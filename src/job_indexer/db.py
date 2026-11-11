from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import JobListing, SourceConfig
from .utils import html_to_text, normalize_key, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS source_instances (
  name TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  tenant TEXT NOT NULL,
  company TEXT NOT NULL,
  base_url TEXT,
  options_json TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  platform TEXT NOT NULL,
  source_instance TEXT NOT NULL,
  external_job_id TEXT NOT NULL,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  description TEXT,
  location TEXT,
  source_url TEXT NOT NULL,
  application_url TEXT,
  salary TEXT,
  employment_type TEXT,
  remote_status TEXT NOT NULL,
  original_posted_at TEXT,
  first_seen_at TEXT NOT NULL,
  last_checked_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  content_hash TEXT,
  last_changed_at TEXT,
  last_seen_at TEXT,
  source_status TEXT NOT NULL DEFAULT 'open',
  missing_scans INTEGER NOT NULL DEFAULT 0,
  last_missing_at TEXT,
  closed_at TEXT,
  canonical_job_id TEXT,
  dedup_reason TEXT,
  dedup_confidence REAL,
  UNIQUE(platform, source_instance, external_job_id)
);

CREATE TABLE IF NOT EXISTS canonical_jobs (
  id TEXT PRIMARY KEY,
  normalized_title TEXT NOT NULL,
  normalized_company TEXT NOT NULL,
  normalized_location TEXT,
  canonical_description TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS canonical_job_search USING fts5(
  canonical_job_id UNINDEXED,
  title,
  company,
  description,
  location
);

CREATE TABLE IF NOT EXISTS job_changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_listing_id INTEGER NOT NULL,
  canonical_job_id TEXT,
  changed_at TEXT NOT NULL,
  field TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT
);

CREATE TABLE IF NOT EXISTS fetch_runs (
  id TEXT PRIMARY KEY,
  source_instance TEXT NOT NULL,
  platform TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  jobs_discovered INTEGER NOT NULL DEFAULT 0,
  jobs_processed INTEGER NOT NULL DEFAULT 0,
  jobs_inserted INTEGER NOT NULL DEFAULT 0,
  jobs_updated INTEGER NOT NULL DEFAULT 0,
  jobs_changed INTEGER NOT NULL DEFAULT 0,
  jobs_missing INTEGER NOT NULL DEFAULT 0,
  jobs_closed INTEGER NOT NULL DEFAULT 0,
  error_details TEXT,
  error_class TEXT,
  duration_ms INTEGER,
  raw_payload_path TEXT,
  pagination_json TEXT
);

"""



INDEXES = """
CREATE INDEX IF NOT EXISTS idx_job_listings_source
  ON job_listings(platform, source_instance);
CREATE INDEX IF NOT EXISTS idx_job_listings_canonical
  ON job_listings(canonical_job_id);
CREATE INDEX IF NOT EXISTS idx_job_listings_status
  ON job_listings(source_status);
CREATE INDEX IF NOT EXISTS idx_canonical_key
  ON canonical_jobs(normalized_company, normalized_title, normalized_location);
CREATE INDEX IF NOT EXISTS idx_canonical_status
  ON canonical_jobs(status);
CREATE INDEX IF NOT EXISTS idx_job_changes_listing
  ON job_changes(job_listing_id, changed_at);
CREATE INDEX IF NOT EXISTS idx_fetch_runs_source
  ON fetch_runs(source_instance, started_at);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    if column not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate(conn: sqlite3.Connection) -> None:
    listing_columns = {
        "content_hash": "TEXT",
        "last_changed_at": "TEXT",
        "last_seen_at": "TEXT",
        "source_status": "TEXT NOT NULL DEFAULT 'open'",
        "missing_scans": "INTEGER NOT NULL DEFAULT 0",
        "last_missing_at": "TEXT",
        "closed_at": "TEXT",
        "canonical_job_id": "TEXT",
        "dedup_reason": "TEXT",
        "dedup_confidence": "REAL",
    }
    for column, definition in listing_columns.items():
        _ensure_column(conn, "job_listings", column, definition)

    run_columns = {
        "jobs_changed": "INTEGER NOT NULL DEFAULT 0",
        "jobs_missing": "INTEGER NOT NULL DEFAULT 0",
        "jobs_closed": "INTEGER NOT NULL DEFAULT 0",
        "error_class": "TEXT",
    }
    for column, definition in run_columns.items():
        _ensure_column(conn, "fetch_runs", column, definition)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.executescript(INDEXES)
    conn.commit()


def upsert_source_instance(conn: sqlite3.Connection, source: SourceConfig) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO source_instances (
          name, platform, tenant, company, base_url, options_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          platform = excluded.platform,
          tenant = excluded.tenant,
          company = excluded.company,
          base_url = excluded.base_url,
          options_json = excluded.options_json,
          updated_at = excluded.updated_at
        """,
        (
            source.name,
            source.platform,
            source.tenant,
            source.company,
            source.base_url,
            json.dumps(source.options, sort_keys=True),
            now,
            now,
        ),
    )
    conn.commit()


def content_hash_for_job(job: JobListing) -> str:
    payload = {
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "location": job.location,
        "source_url": job.source_url,
        "application_url": job.application_url,
        "salary": job.salary,
        "employment_type": job.employment_type,
        "remote_status": job.remote_status,
        "original_posted_at": job.original_posted_at,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _description_similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    left_text = html_to_text(left).lower()
    right_text = html_to_text(right).lower()
    if not left_text or not right_text:
        return None
    return SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()


def _url_candidate(
    conn: sqlite3.Connection,
    job: JobListing,
) -> str | None:
    urls = [job.source_url]
    if job.application_url:
        urls.append(job.application_url)
    placeholders = ",".join("?" for _ in urls)
    row = conn.execute(
        f"""
        SELECT canonical_job_id FROM job_listings
        WHERE canonical_job_id IS NOT NULL
          AND (source_url IN ({placeholders}) OR application_url IN ({placeholders}))
        LIMIT 1
        """,
        (*urls, *urls),
    ).fetchone()
    return str(row["canonical_job_id"]) if row is not None else None


def _canonical_candidates(
    conn: sqlite3.Connection,
    job: JobListing,
) -> list[sqlite3.Row]:
    normalized_title = normalize_key(job.title)
    normalized_company = normalize_key(job.company)
    normalized_location = normalize_key(job.location)
    if normalized_location is None:
        return list(
            conn.execute(
                """
                SELECT * FROM canonical_jobs
                WHERE normalized_title = ?
                  AND normalized_company = ?
                  AND normalized_location IS NULL
                  AND status != 'closed'
                ORDER BY created_at
                """,
                (normalized_title, normalized_company),
            )
        )
    return list(
        conn.execute(
            """
            SELECT * FROM canonical_jobs
            WHERE normalized_title = ?
              AND normalized_company = ?
              AND normalized_location = ?
              AND status != 'closed'
            ORDER BY created_at
            """,
            (normalized_title, normalized_company, normalized_location),
        )
    )


def _resolve_canonical(
    conn: sqlite3.Connection,
    job: JobListing,
    now: str,
) -> tuple[str, str, float]:
    url_match = _url_candidate(conn, job)
    if url_match is not None:
        _touch_canonical(conn, url_match, job, now)
        return url_match, "source_or_application_url_exact", 1.0

    normalized_title = normalize_key(job.title)
    normalized_company = normalize_key(job.company)
    normalized_location = normalize_key(job.location)

    for candidate in _canonical_candidates(conn, job):
        similarity = _description_similarity(
            job.description,
            candidate["canonical_description"],
        )
        if similarity is not None and similarity < 0.55:
            continue
        canonical_id = str(candidate["id"])
        _touch_canonical(conn, canonical_id, job, now)
        return canonical_id, "company_title_location_exact", 1.0

    canonical_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO canonical_jobs (
          id, normalized_title, normalized_company, normalized_location,
          canonical_description, status, first_seen_at, last_seen_at,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
        """,
        (
            canonical_id,
            normalized_title,
            normalized_company,
            normalized_location,
            job.description,
            now,
            now,
            now,
            now,
        ),
    )
    return canonical_id, "new_canonical_job", 1.0


def _touch_canonical(
    conn: sqlite3.Connection,
    canonical_id: str,
    job: JobListing,
    now: str,
) -> None:
    row = conn.execute(
        "SELECT canonical_description FROM canonical_jobs WHERE id = ?",
        (canonical_id,),
    ).fetchone()
    if row is None:
        return
    description = row["canonical_description"]
    if job.description and (
        not description or len(job.description) > len(description)
    ):
        description = job.description
    conn.execute(
        """
        UPDATE canonical_jobs SET
          canonical_description = ?,
          status = 'open',
          last_seen_at = ?,
          updated_at = ?
        WHERE id = ?
        """,
        (description, now, now, canonical_id),
    )


def _refresh_search_index(
    conn: sqlite3.Connection,
    canonical_ids: Iterable[str],
) -> None:
    for canonical_id in sorted(set(canonical_ids)):
        conn.execute(
            "DELETE FROM canonical_job_search WHERE canonical_job_id = ?",
            (canonical_id,),
        )
        row = conn.execute(
            "SELECT * FROM canonical_jobs WHERE id = ?",
            (canonical_id,),
        ).fetchone()
        if row is None:
            continue
        conn.execute(
            """
            INSERT INTO canonical_job_search (
              canonical_job_id, title, company, description, location
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                canonical_id,
                row["normalized_title"].replace("-", " "),
                row["normalized_company"].replace("-", " "),
                html_to_text(row["canonical_description"]),
                (row["normalized_location"] or "").replace("-", " "),
            ),
        )


def _record_changes(
    conn: sqlite3.Connection,
    listing_id: int,
    canonical_id: str,
    old: sqlite3.Row,
    job: JobListing,
    now: str,
) -> None:
    fields = (
        "title",
        "company",
        "description",
        "location",
        "source_url",
        "application_url",
        "salary",
        "employment_type",
        "remote_status",
        "original_posted_at",
    )
    for field in fields:
        old_value = old[field]
        new_value = getattr(job, field)
        if old_value != new_value:
            conn.execute(
                """
                INSERT INTO job_changes (
                  job_listing_id, canonical_job_id, changed_at, field,
                  old_value, new_value
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (listing_id, canonical_id, now, field, old_value, new_value),
            )


def upsert_jobs(
    conn: sqlite3.Connection,
    jobs: Sequence[JobListing],
) -> tuple[int, int, int]:
    if not jobs:
        return 0, 0, 0

    source = jobs[0]
    existing = {
        row["external_job_id"]: row
        for row in conn.execute(
            "SELECT * FROM job_listings WHERE platform = ? AND source_instance = ?",
            (source.platform, source.source_instance),
        )
    }

    inserted = 0
    updated = 0
    changed = 0
    now = utc_now_iso()
    touched_canonicals: set[str] = set()

    for job in jobs:
        old = existing.get(job.external_job_id)
        digest = content_hash_for_job(job)

        if old is None:
            canonical_id, reason, confidence = _resolve_canonical(conn, job, now)
            cursor = conn.execute(
                """
                INSERT INTO job_listings (
                  platform, source_instance, external_job_id, title, company, description,
                  location, source_url, application_url, salary, employment_type,
                  remote_status, original_posted_at, first_seen_at, last_checked_at,
                  created_at, updated_at, content_hash, last_changed_at, last_seen_at,
                  source_status, missing_scans, canonical_job_id, dedup_reason,
                  dedup_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'open', 0, ?, ?, ?)
                """,
                (
                    job.platform,
                    job.source_instance,
                    job.external_job_id,
                    job.title,
                    job.company,
                    job.description,
                    job.location,
                    job.source_url,
                    job.application_url,
                    job.salary,
                    job.employment_type,
                    job.remote_status,
                    job.original_posted_at,
                    job.first_seen_at,
                    job.last_checked_at,
                    now,
                    now,
                    digest,
                    now,
                    job.last_checked_at,
                    canonical_id,
                    reason,
                    confidence,
                ),
            )
            inserted += 1
            listing_id = int(cursor.lastrowid)
        else:
            canonical_id = old["canonical_job_id"] or _resolve_canonical(conn, job, now)[0]
            is_changed = old["content_hash"] != digest
            if is_changed:
                changed += 1
                _record_changes(conn, int(old["id"]), canonical_id, old, job, now)
                last_changed_at = now
            else:
                last_changed_at = old["last_changed_at"] or now
            conn.execute(
                """
                UPDATE job_listings SET
                  title = ?, company = ?, description = ?, location = ?,
                  source_url = ?, application_url = ?, salary = ?,
                  employment_type = ?, remote_status = ?, original_posted_at = ?,
                  last_checked_at = ?, last_seen_at = ?, updated_at = ?,
                  content_hash = ?, last_changed_at = ?, source_status = 'open',
                  missing_scans = 0, last_missing_at = NULL, closed_at = NULL,
                  canonical_job_id = ?
                WHERE id = ?
                """,
                (
                    job.title,
                    job.company,
                    job.description,
                    job.location,
                    job.source_url,
                    job.application_url,
                    job.salary,
                    job.employment_type,
                    job.remote_status,
                    job.original_posted_at,
                    job.last_checked_at,
                    job.last_checked_at,
                    now,
                    digest,
                    last_changed_at,
                    canonical_id,
                    old["id"],
                ),
            )
            updated += 1
            listing_id = int(old["id"])
            _touch_canonical(conn, canonical_id, job, now)

        touched_canonicals.add(canonical_id)
        existing[job.external_job_id] = conn.execute(
            "SELECT * FROM job_listings WHERE id = ?", (listing_id,)
        ).fetchone()

    _refresh_search_index(conn, touched_canonicals)
    conn.commit()
    return inserted, updated, changed


def apply_source_scan(
    conn: sqlite3.Connection,
    *,
    source: SourceConfig,
    seen_external_ids: Iterable[str],
    checked_at: str,
    complete: bool,
) -> tuple[int, int]:
    if not complete:
        return 0, 0

    seen = {str(item) for item in seen_external_ids}
    rows = list(
        conn.execute(
            """
            SELECT id, external_job_id, missing_scans, canonical_job_id
            FROM job_listings
            WHERE platform = ? AND source_instance = ? AND source_status != 'closed'
            """,
            (source.platform, source.name),
        )
    )
    missing = 0
    closed = 0
    touched_canonicals: set[str] = set()

    for row in rows:
        if str(row["external_job_id"]) in seen:
            continue
        missing += 1
        missing_scans = int(row["missing_scans"] or 0) + 1
        status = "closed" if missing_scans >= 2 else "missing"
        if status == "closed":
            closed += 1
        conn.execute(
            """
            UPDATE job_listings SET
              missing_scans = ?, last_missing_at = ?, source_status = ?,
              closed_at = CASE WHEN ? = 'closed' THEN ? ELSE closed_at END,
              updated_at = ?
            WHERE id = ?
            """,
            (
                missing_scans,
                checked_at,
                status,
                status,
                checked_at,
                checked_at,
                row["id"],
            ),
        )
        if row["canonical_job_id"]:
            touched_canonicals.add(str(row["canonical_job_id"]))

    for canonical_id in touched_canonicals:
        _recompute_canonical_status(conn, canonical_id, checked_at)
    _refresh_search_index(conn, touched_canonicals)
    conn.commit()
    return missing, closed


def _recompute_canonical_status(
    conn: sqlite3.Connection,
    canonical_id: str,
    now: str,
) -> None:
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN source_status IN ('open', 'missing') THEN 1 ELSE 0 END) AS active,
          SUM(CASE WHEN source_status = 'open' THEN 1 ELSE 0 END) AS open_count
        FROM job_listings WHERE canonical_job_id = ?
        """,
        (canonical_id,),
    ).fetchone()
    if row is None:
        return
    active = int(row["active"] or 0)
    open_count = int(row["open_count"] or 0)
    status = "open" if active > 0 else "closed"
    conn.execute(
        """
        UPDATE canonical_jobs SET status = ?, updated_at = ?
        WHERE id = ? AND status != ?
        """,
        (status, now, canonical_id, status),
    )
    if open_count > 0:
        conn.execute(
            "UPDATE canonical_jobs SET last_seen_at = ? WHERE id = ?",
            (now, canonical_id),
        )


def rebuild_dedup(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM job_changes")
    conn.execute("DELETE FROM canonical_job_search")
    conn.execute("DELETE FROM canonical_jobs")
    conn.execute(
        """
        UPDATE job_listings SET
          canonical_job_id = NULL, dedup_reason = NULL, dedup_confidence = NULL
        """
    )
    rows = list(conn.execute("SELECT * FROM job_listings ORDER BY id"))
    touched: set[str] = set()
    now = utc_now_iso()
    for row in rows:
        job = JobListing(
            platform=row["platform"],
            source_instance=row["source_instance"],
            external_job_id=row["external_job_id"],
            title=row["title"],
            company=row["company"],
            description=row["description"],
            location=row["location"],
            source_url=row["source_url"],
            application_url=row["application_url"],
            salary=row["salary"],
            employment_type=row["employment_type"],
            remote_status=row["remote_status"],
            original_posted_at=row["original_posted_at"],
            first_seen_at=row["first_seen_at"],
            last_checked_at=row["last_checked_at"],
        )
        canonical_id, reason, confidence = _resolve_canonical(conn, job, now)
        conn.execute(
            """
            UPDATE job_listings SET
              canonical_job_id = ?, dedup_reason = ?, dedup_confidence = ?
            WHERE id = ?
            """,
            (canonical_id, reason, confidence, row["id"]),
        )
        touched.add(canonical_id)
    _refresh_search_index(conn, touched)
    conn.commit()
    return len(touched)


def create_fetch_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    source: SourceConfig,
    started_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fetch_runs (
          id, source_instance, platform, started_at, status
        ) VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (run_id, source.name, source.platform, started_at),
    )
    conn.commit()


def finish_fetch_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    completed_at: str,
    status: str,
    jobs_discovered: int,
    jobs_processed: int,
    jobs_inserted: int,
    jobs_updated: int,
    error_details: str | None,
    duration_ms: int,
    raw_payload_path: str | None,
    pagination: dict[str, Any],
    jobs_changed: int = 0,
    jobs_missing: int = 0,
    jobs_closed: int = 0,
    error_class: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE fetch_runs SET
          completed_at = ?,
          status = ?,
          jobs_discovered = ?,
          jobs_processed = ?,
          jobs_inserted = ?,
          jobs_updated = ?,
          jobs_changed = ?,
          jobs_missing = ?,
          jobs_closed = ?,
          error_details = ?,
          error_class = ?,
          duration_ms = ?,
          raw_payload_path = ?,
          pagination_json = ?
        WHERE id = ?
        """,
        (
            completed_at,
            status,
            jobs_discovered,
            jobs_processed,
            jobs_inserted,
            jobs_updated,
            jobs_changed,
            jobs_missing,
            jobs_closed,
            error_details,
            error_class,
            duration_ms,
            raw_payload_path,
            json.dumps(pagination, sort_keys=True),
            run_id,
        ),
    )
    conn.commit()


def get_fetch_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM fetch_runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row is not None else None


def get_job_count(conn: sqlite3.Connection, source_instance: str | None = None) -> int:
    if source_instance is None:
        row = conn.execute("SELECT COUNT(*) AS count FROM job_listings").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM job_listings WHERE source_instance = ?",
            (source_instance,),
        ).fetchone()
    return int(row["count"])


def get_job_by_external_id(
    conn: sqlite3.Connection,
    *,
    platform: str,
    source_instance: str,
    external_job_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM job_listings
        WHERE platform = ? AND source_instance = ? AND external_job_id = ?
        """,
        (platform, source_instance, external_job_id),
    ).fetchone()
    return dict(row) if row is not None else None


def _fts_query(value: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", value)
    return " OR ".join(f'"{token}"' for token in tokens)


def search_jobs(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    company: str | None = None,
    location: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "relevance",
) -> tuple[list[dict[str, Any]], int]:
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    where: list[str] = []
    params: list[Any] = []
    joins = ""

    fts_query = _fts_query(q) if q and q.strip() else ""
    if fts_query:
        joins = "JOIN canonical_job_search fts ON fts.canonical_job_id = c.id"
        where.append("canonical_job_search MATCH ?")
        params.append(fts_query)
    if company:
        where.append("c.normalized_company LIKE ?")
        params.append(f"%{normalize_key(company)}%")
    if location:
        where.append("COALESCE(c.normalized_location, '') LIKE ?")
        params.append(f"%{normalize_key(location)}%")
    if platform:
        where.append(
            "EXISTS (SELECT 1 FROM job_listings jl WHERE jl.canonical_job_id = c.id AND jl.platform = ?)"
        )
        params.append(platform)
    if status:
        where.append("c.status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if sort == "newest":
        order = "c.updated_at DESC, c.id"
    elif sort == "oldest":
        order = "c.created_at ASC, c.id"
    elif fts_query:
        order = "rank, c.updated_at DESC"
    else:
        order = "c.updated_at DESC, c.id"

    count_sql = f"SELECT COUNT(*) AS count FROM canonical_jobs c {joins} {where_sql}"
    total = int(conn.execute(count_sql, params).fetchone()["count"])

    rows = conn.execute(
        f"""
        SELECT c.*,
          (SELECT COUNT(*) FROM job_listings jl WHERE jl.canonical_job_id = c.id) AS source_count
        FROM canonical_jobs c
        {joins}
        {where_sql}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return [dict(row) for row in rows], total


def get_canonical_job(conn: sqlite3.Connection, canonical_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM canonical_jobs WHERE id = ?",
        (canonical_id,),
    ).fetchone()
    if row is None:
        return None
    job = dict(row)
    job["source_count"] = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM job_listings WHERE canonical_job_id = ?",
            (canonical_id,),
        ).fetchone()["count"]
    )
    job["sources"] = [
        dict(source)
        for source in conn.execute(
            """
            SELECT * FROM job_listings WHERE canonical_job_id = ?
            ORDER BY last_checked_at DESC, id
            """,
            (canonical_id,),
        )
    ]
    return job


def get_source_status(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.*,
          (SELECT COUNT(*) FROM job_listings jl WHERE jl.source_instance = s.name) AS job_count,
          (SELECT status FROM fetch_runs fr WHERE fr.source_instance = s.name
             ORDER BY started_at DESC LIMIT 1) AS last_status,
          (SELECT started_at FROM fetch_runs fr WHERE fr.source_instance = s.name
             ORDER BY started_at DESC LIMIT 1) AS last_run_at,
          (SELECT completed_at FROM fetch_runs fr WHERE fr.source_instance = s.name
             AND fr.status = 'SUCCESS' ORDER BY started_at DESC LIMIT 1) AS last_success_at,
          (SELECT completed_at FROM fetch_runs fr WHERE fr.source_instance = s.name
             AND fr.status IN ('SUCCESS', 'PARTIAL_SUCCESS')
             ORDER BY started_at DESC LIMIT 1) AS last_evidence_at
        FROM source_instances s
        ORDER BY s.platform, s.name
        """
    )
    return [dict(row) for row in rows]


def get_recent_fetch_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM fetch_runs ORDER BY started_at DESC LIMIT ?",
        (max(1, min(int(limit), 200)),),
    )
    return [dict(row) for row in rows]
