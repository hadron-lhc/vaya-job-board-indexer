from __future__ import annotations

from pathlib import Path

from job_indexer.db import (
    connect,
    create_fetch_run,
    finish_fetch_run,
    get_fetch_run,
    get_job_by_external_id,
    get_job_count,
    init_db,
    upsert_jobs,
    upsert_source_instance,
)
from job_indexer.models import JobListing, SourceConfig


SOURCE = SourceConfig(
    name="greenhouse-stripe",
    platform="greenhouse",
    tenant="stripe",
    company="Stripe",
)


def make_job(
    *,
    external_job_id: str = "1",
    title: str = "Engineer",
    first_seen_at: str = "2026-01-01T00:00:00+00:00",
    last_checked_at: str = "2026-01-02T00:00:00+00:00",
) -> JobListing:
    return JobListing(
        platform="greenhouse",
        source_instance="greenhouse-stripe",
        external_job_id=external_job_id,
        title=title,
        company="Stripe",
        description="<p>Job</p>",
        location="Remote",
        source_url=f"https://example.test/jobs/{external_job_id}",
        application_url=None,
        salary=None,
        employment_type=None,
        remote_status="remote",
        original_posted_at="2026-01-01T00:00:00+00:00",
        first_seen_at=first_seen_at,
        last_checked_at=last_checked_at,
    )


def test_upsert_jobs_is_idempotent_and_preserves_first_seen(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)

    inserted, updated, changed = upsert_jobs(conn, [make_job()])
    assert (inserted, updated, changed) == (1, 0, 0)
    assert get_job_count(conn, SOURCE.name) == 1

    inserted, updated, changed = upsert_jobs(
        conn,
        [
            make_job(
                title="Senior Engineer",
                first_seen_at="2026-02-01T00:00:00+00:00",
                last_checked_at="2026-02-02T00:00:00+00:00",
            )
        ],
    )
    assert (inserted, updated, changed) == (0, 1, 1)
    assert get_job_count(conn, SOURCE.name) == 1

    stored = get_job_by_external_id(
        conn,
        platform="greenhouse",
        source_instance="greenhouse-stripe",
        external_job_id="1",
    )
    assert stored is not None
    assert stored["title"] == "Senior Engineer"
    assert stored["first_seen_at"] == "2026-01-01T00:00:00+00:00"
    assert stored["last_checked_at"] == "2026-02-02T00:00:00+00:00"
    conn.close()


def test_duplicate_external_ids_in_one_batch_do_not_duplicate_rows(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)

    inserted, updated, changed = upsert_jobs(conn, [make_job(), make_job(title="Updated Engineer")])

    assert (inserted, updated, changed) == (1, 1, 1)
    assert get_job_count(conn, SOURCE.name) == 1
    stored = get_job_by_external_id(
        conn,
        platform="greenhouse",
        source_instance="greenhouse-stripe",
        external_job_id="1",
    )
    assert stored is not None
    assert stored["title"] == "Updated Engineer"
    conn.close()


def test_fetch_run_lifecycle_is_recorded(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    create_fetch_run(conn, run_id="run-1", source=SOURCE, started_at="2026-01-01T00:00:00+00:00")
    finish_fetch_run(
        conn,
        run_id="run-1",
        completed_at="2026-01-01T00:00:01+00:00",
        status="success",
        jobs_discovered=3,
        jobs_processed=3,
        jobs_inserted=2,
        jobs_updated=1,
        error_details=None,
        duration_ms=1000,
        raw_payload_path="artifacts/raw/example.json",
        pagination={"pages": 1},
    )

    run = get_fetch_run(conn, "run-1")
    assert run is not None
    assert run["status"] == "success"
    assert run["jobs_discovered"] == 3
    assert run["jobs_processed"] == 3
    assert run["jobs_inserted"] == 2
    assert run["jobs_updated"] == 1
    assert run["error_details"] is None
    conn.close()


def test_init_db_migrates_legacy_tables_before_creating_indexes(tmp_path: Path) -> None:
    conn = connect(tmp_path / "legacy.db")
    conn.executescript(
        """
        CREATE TABLE job_listings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          platform TEXT NOT NULL,
          source_instance TEXT NOT NULL,
          external_job_id TEXT NOT NULL,
          title TEXT NOT NULL,
          company TEXT NOT NULL,
          source_url TEXT NOT NULL,
          remote_status TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_checked_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(platform, source_instance, external_job_id)
        );
        CREATE TABLE fetch_runs (
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
        """
    )

    init_db(conn)

    listing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(job_listings)")}
    run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(fetch_runs)")}
    assert {"canonical_job_id", "source_status", "missing_scans", "closed_at"} <= listing_columns
    assert {"jobs_changed", "jobs_missing", "jobs_closed", "error_class"} <= run_columns
    indexes = {row["name"] for row in conn.execute("PRAGMA index_list(job_listings)")}
    assert "idx_job_listings_canonical" in indexes
    assert "idx_job_listings_status" in indexes
    conn.close()
