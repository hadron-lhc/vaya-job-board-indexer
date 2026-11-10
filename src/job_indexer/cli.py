from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .api import serve
from .config import load_sources
from .connectors.registry import SUPPORTED_PLATFORMS, build_connector
from .coverage import build_coverage
from .db import connect, init_db, rebuild_dedup
from .http import HttpClient
from .runner import run_fetch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-indexer",
        description="Multi-tenant job board indexer with search API and UI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch and persist one source instance.")
    fetch_parser.add_argument("--platform", required=True, choices=SUPPORTED_PLATFORMS)
    fetch_parser.add_argument("--source", required=True, help="Source instance name from config.")
    fetch_parser.add_argument("--config", default="config/sources.json")
    fetch_parser.add_argument("--db", default="data/jobs.db")
    fetch_parser.add_argument("--artifacts-dir", default="artifacts")

    all_parser = subparsers.add_parser("fetch-all", help="Refresh every configured source.")
    all_parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS)
    all_parser.add_argument("--source", action="append", default=None)
    all_parser.add_argument("--config", default="config/sources.json")
    all_parser.add_argument("--db", default="data/jobs.db")
    all_parser.add_argument("--artifacts-dir", default="artifacts")
    all_parser.add_argument("--json", action="store_true", help="Print full JSON results.")

    list_parser = subparsers.add_parser("list-sources", help="List configured source instances.")
    list_parser.add_argument("--config", default="config/sources.json")

    coverage_parser = subparsers.add_parser("coverage", help="Print platform coverage JSON.")
    coverage_parser.add_argument("--db", default="data/jobs.db")
    coverage_parser.add_argument("--matrix", default=None)

    dedupe_parser = subparsers.add_parser("rebuild-dedup", help="Rebuild canonical jobs from listings.")
    dedupe_parser.add_argument("--db", default="data/jobs.db")

    serve_parser = subparsers.add_parser("serve", help="Start the HTTP API and search UI.")
    serve_parser.add_argument("--db", default="data/jobs.db")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--matrix", default=None)

    return parser


def _exit_code(results: list[Any]) -> int:
    statuses = {result.status for result in results}
    if "FAILED" in statuses or any(
        status
        in {"RATE_LIMITED", "UNAUTHORIZED", "BLOCKED", "TIMEOUT", "SCHEMA_CHANGED"}
        for status in statuses
    ):
        return 1
    if "PARTIAL_SUCCESS" in statuses:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"coverage", "rebuild-dedup", "serve"}:
        if args.command == "serve":
            serve(
                args.db,
                host=args.host,
                port=args.port,
                matrix_path=args.matrix,
            )
            return 0
        conn = connect(args.db)
        init_db(conn)
        try:
            if args.command == "coverage":
                print(
                    json.dumps(
                        build_coverage(conn, matrix_path=args.matrix),
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                count = rebuild_dedup(conn)
                print(f"Rebuilt {count} canonical job(s).")
        finally:
            conn.close()
        return 0

    try:
        sources = load_sources(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "list-sources":
        for source in sources.values():
            print(f"{source.name}\t{source.platform}\t{source.tenant}\t{source.company}")
        return 0

    if args.command == "fetch-all":
        selected = list(sources.values())
        if args.platform:
            selected = [source for source in selected if source.platform == args.platform]
        if args.source:
            requested = set(args.source)
            missing = requested - set(sources)
            if missing:
                print(
                    f"error: source(s) not configured: {', '.join(sorted(missing))}",
                    file=sys.stderr,
                )
                return 1
            selected = [source for source in selected if source.name in requested]
        if not selected:
            print("error: no sources selected", file=sys.stderr)
            return 1

        results = []
        with HttpClient() as http:
            for source in selected:
                connector = build_connector(source.platform, http)
                result = run_fetch(
                    source,
                    connector,
                    db_path=args.db,
                    artifacts_dir=args.artifacts_dir,
                )
                results.append(result)
                print(
                    f"{result.source.name}\t{result.status}\t"
                    f"{result.jobs_processed}/{result.jobs_discovered}\t"
                    f"+{result.jobs_inserted} ~{result.jobs_updated} "
                    f"!{result.jobs_changed} -{result.jobs_closed}",
                    file=sys.stderr,
                )
        payload = [result.to_dict() for result in results]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return _exit_code(results)

    source = sources.get(args.source)
    if source is None:
        print(f"error: source {args.source!r} is not configured", file=sys.stderr)
        return 1
    if source.platform != args.platform:
        print(
            f"error: source {source.name!r} is platform {source.platform!r}, "
            f"not {args.platform!r}",
            file=sys.stderr,
        )
        return 1

    with HttpClient() as http:
        connector = build_connector(source.platform, http)
        result = run_fetch(
            source,
            connector,
            db_path=args.db,
            artifacts_dir=args.artifacts_dir,
        )

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return _exit_code([result])
