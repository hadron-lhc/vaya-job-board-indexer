from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from .coverage import build_coverage
from .db import (
    connect,
    get_canonical_job,
    get_job_count,
    get_recent_fetch_runs,
    get_source_status,
    init_db,
    search_jobs,
)


def _json_default(value: Any) -> Any:
    return str(value)


def _parse_int(
    params: dict[str, list[str]],
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = params.get(key, [str(default)])[0]
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _one(params: dict[str, list[str]], key: str) -> str | None:
    value = params.get(key, [""])[0].strip()
    return value or None


class JobIndexerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        db_path: str | Path,
        matrix_path: str | Path | None = None,
    ) -> None:
        super().__init__(server_address, JobIndexerRequestHandler)
        self.db_path = str(db_path)
        self.matrix_path = matrix_path


class JobIndexerRequestHandler(BaseHTTPRequestHandler):
    server: JobIndexerHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/health":
                self._json(self._health())
            elif path == "/api/v1/jobs":
                self._json(self._jobs(params))
            elif path.startswith("/api/v1/jobs/"):
                job_id = path.removeprefix("/api/v1/jobs/")
                self._json(self._job(job_id))
            elif path == "/api/v1/sources":
                self._json(self._sources())
            elif path == "/api/v1/coverage":
                self._json(self._coverage())
            elif path == "/api/v1/fetch-runs":
                self._json(self._fetch_runs(params))
            elif path == "/":
                self._html(self._index(params))
            elif path == "/coverage":
                self._html(self._coverage_page())
            else:
                self._json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception as exc:  # pragma: no cover - defensive boundary
            self._json(
                {"error": f"{type(exc).__name__}: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _connection(self):
        conn = connect(self.server.db_path)
        init_db(conn)
        return conn

    def _health(self) -> dict[str, Any]:
        conn = self._connection()
        try:
            return {
                "status": "ok",
                "database": "ok",
                "jobs": get_job_count(conn),
            }
        finally:
            conn.close()

    def _jobs(self, params: dict[str, list[str]]) -> dict[str, Any]:
        limit = _parse_int(params, "limit", 20, minimum=1, maximum=100)
        offset = _parse_int(params, "offset", 0, minimum=0, maximum=1_000_000)
        sort = _one(params, "sort") or "relevance"
        if sort not in {"relevance", "newest", "oldest"}:
            raise ValueError("sort must be relevance, newest, or oldest")
        status = _one(params, "status")
        if status is not None and status not in {"open", "closed"}:
            raise ValueError("status must be open or closed")
        conn = self._connection()
        try:
            items, total = search_jobs(
                conn,
                q=_one(params, "q"),
                company=_one(params, "company"),
                location=_one(params, "location"),
                platform=_one(params, "platform"),
                status=status,
                limit=limit,
                offset=offset,
                sort=sort,
            )
        finally:
            conn.close()
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }

    def _job(self, job_id: str) -> dict[str, Any]:
        if not job_id or "/" in job_id:
            raise ValueError("invalid job id")
        conn = self._connection()
        try:
            job = get_canonical_job(conn, job_id)
        finally:
            conn.close()
        if job is None:
            raise LookupError("job not found")
        return job

    def _sources(self) -> dict[str, Any]:
        conn = self._connection()
        try:
            return {"items": get_source_status(conn)}
        finally:
            conn.close()

    def _coverage(self) -> dict[str, Any]:
        conn = self._connection()
        try:
            return build_coverage(conn, matrix_path=self.server.matrix_path)
        finally:
            conn.close()

    def _fetch_runs(self, params: dict[str, list[str]]) -> dict[str, Any]:
        limit = _parse_int(params, "limit", 50, minimum=1, maximum=200)
        conn = self._connection()
        try:
            return {"items": get_recent_fetch_runs(conn, limit=limit)}
        finally:
            conn.close()

    def _index(self, params: dict[str, list[str]]) -> str:
        q = _one(params, "q") or ""
        company = _one(params, "company") or ""
        location = _one(params, "location") or ""
        status = _one(params, "status") or "open"
        limit = _parse_int(params, "limit", 20, minimum=1, maximum=100)
        offset = _parse_int(params, "offset", 0, minimum=0, maximum=1_000_000)

        conn = self._connection()
        try:
            items, total = search_jobs(
                conn,
                q=q or None,
                company=company or None,
                location=location or None,
                status=status,
                limit=limit,
                offset=offset,
                sort="relevance" if q else "newest",
            )
            details = [get_canonical_job(conn, item["id"]) for item in items]
        finally:
            conn.close()

        cards: list[str] = []
        for item in details:
            if item is None:
                continue
            links: list[str] = []
            for source in item["sources"]:
                source_url = html.escape(source["source_url"], quote=True)
                links.append(
                    f'<a href="{source_url}" rel="noopener noreferrer" target="_blank">'
                    f'{html.escape(source["platform"])} listing</a>'
                )
                if source.get("application_url"):
                    apply_url = html.escape(source["application_url"], quote=True)
                    links.append(
                        f'<a class="apply" href="{apply_url}" rel="noopener noreferrer" '
                        f'target="_blank">Apply</a>'
                    )
            description = html.escape(
                (item.get("canonical_description") or "")[:400]
            )
            cards.append(
                f"""
                <article class="job">
                  <h2>{html.escape(item["normalized_title"].replace("-", " ").title())}</h2>
                  <p class="meta">{html.escape(item["normalized_company"].replace("-", " ").title())}
                    &middot; {html.escape((item["normalized_location"] or "Location not specified").replace("-", " ").title())}
                    &middot; <span class="status {html.escape(item["status"])}">{html.escape(item["status"])}</span>
                    &middot; {item["source_count"]} source(s)</p>
                  <p class="description">{description}</p>
                  <p class="links">{' '.join(links)}</p>
                </article>
                """
            )

        next_offset = offset + limit
        prev_offset = max(0, offset - limit)
        pager: list[str] = []
        if offset > 0:
            pager.append(
                f'<a href="/?{urlencode({"q": q, "company": company, "location": location, "status": status, "offset": prev_offset, "limit": limit})}">Previous</a>'
            )
        if next_offset < total:
            pager.append(
                f'<a href="/?{urlencode({"q": q, "company": company, "location": location, "status": status, "offset": next_offset, "limit": limit})}">Next</a>'
            )

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vaya Job Index</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #17202a; }}
    form {{ display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: .5rem; margin-bottom: 1.5rem; }}
    input, select, button {{ padding: .55rem; font: inherit; }}
    .job {{ border: 1px solid #d5d8dc; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
    h2 {{ margin: 0 0 .35rem; font-size: 1.1rem; }}
    .meta, .description {{ color: #566573; margin: .35rem 0; }}
    .links a {{ margin-right: .8rem; }}
    .apply {{ font-weight: 600; }}
    .status {{ text-transform: uppercase; font-size: .75rem; }}
    .closed {{ color: #b03a2e; }}
    .open {{ color: #1e8449; }}
    nav {{ display: flex; gap: 1rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <nav><a href="/">Jobs</a><a href="/coverage">Coverage</a><a href="/api/v1/jobs">API</a></nav>
  <h1>Vaya Job Index</h1>
  <form method="get" action="/">
    <input name="q" placeholder="Search title or description" value="{html.escape(q, quote=True)}">
    <input name="company" placeholder="Company" value="{html.escape(company, quote=True)}">
    <input name="location" placeholder="Location" value="{html.escape(location, quote=True)}">
    <select name="status">
      <option value="open" {"selected" if status == "open" else ""}>Open</option>
      <option value="closed" {"selected" if status == "closed" else ""}>Closed</option>
      <option value="" {"selected" if status == "" else ""}>All</option>
    </select>
    <button type="submit">Search</button>
  </form>
  <p>{total} job(s) found.</p>
  {''.join(cards) or '<p>No jobs found. Run an indexer fetch first.</p>'}
  <nav>{' '.join(pager)}</nav>
</body>
</html>"""

    def _coverage_page(self) -> str:
        coverage = self._coverage()
        rows = "".join(
            f"<tr><td>{html.escape(item['platform'])}</td>"
            f"<td>{html.escape(item['category'])}</td>"
            f"<td>{html.escape(item['implementation_status'])}</td>"
            f"<td>{item['source_instances']}</td><td>{item['jobs']}</td></tr>"
            for item in coverage["platforms"]
        )
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Coverage</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d5d8dc;padding:.4rem;text-align:left}}
</style></head><body>
<nav><a href="/">Jobs</a> <a href="/api/v1/coverage">Coverage JSON</a></nav>
<h1>Coverage</h1>
<p>Required platforms: {coverage['total_required']}; source instances: {coverage['source_instances']};
jobs: {coverage['total_jobs']}.</p>
<p>Status counts: {html.escape(json.dumps(coverage['status_counts']))}</p>
<table><thead><tr><th>Platform</th><th>Category</th><th>Status</th><th>Sources</th><th>Jobs</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>"""

    def _json(self, payload: Any, *, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body_text: str, *, status: int = HTTPStatus.OK) -> None:
        body = body_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(
    db_path: str | Path = "data/jobs.db",
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    matrix_path: str | Path | None = None,
) -> JobIndexerHTTPServer:
    return JobIndexerHTTPServer(
        (host, port),
        db_path=db_path,
        matrix_path=matrix_path,
    )


def serve(
    db_path: str | Path = "data/jobs.db",
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    matrix_path: str | Path | None = None,
) -> None:
    server = create_server(db_path, host=host, port=port, matrix_path=matrix_path)
    print(f"Serving job index at http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
