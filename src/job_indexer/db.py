from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from .models import JobListing, SourceConfig
from .utils import utc_now_iso


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
  UNIQUE(platform, source_instance, external_job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_listings_source
  ON job_listings(platform, source_instance);

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
  error_details TEXT,
  duration_ms INTEGER,
  raw_payload_path TEXT,
  pagination_json TEXT
);

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


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
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


def upsert_jobs(conn: sqlite3.Connection, jobs: Sequence[JobListing]) -> tuple[int, int]:
    if not jobs:
        return 0, 0

    source = jobs[0]
    existing_ids = {
        row["external_job_id"]
        for row in conn.execute(
            "SELECT external_job_id FROM job_listings WHERE platform = ? AND source_instance = ?",
            (source.platform, source.source_instance),
        )
    }

    inserted = 0
    updated = 0
    now = utc_now_iso()

    for job in jobs:
        was_existing = job.external_job_id in existing_ids
        conn.execute(
            """
            INSERT INTO job_listings (
              platform, source_instance, external_job_id, title, company, description,
              location, source_url, application_url, salary, employment_type,
              remote_status, original_posted_at, first_seen_at, last_checked_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, source_instance, external_job_id) DO UPDATE SET
              title = excluded.title,
              company = excluded.company,
              description = excluded.description,
              location = excluded.location,
              source_url = excluded.source_url,
              application_url = excluded.application_url,
              salary = excluded.salary,
              employment_type = excluded.employment_type,
              remote_status = excluded.remote_status,
              original_posted_at = excluded.original_posted_at,
              last_checked_at = excluded.last_checked_at,
              updated_at = excluded.updated_at
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
            ),
        )
        if was_existing:
            updated += 1
        else:
            inserted += 1
            existing_ids.add(job.external_job_id)

    conn.commit()
    return inserted, updated


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
        ) VALUES (?, ?, ?, ?, 'running')
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
          error_details = ?,
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
            error_details,
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
