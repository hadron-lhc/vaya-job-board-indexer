from __future__ import annotations

from pathlib import Path

from job_indexer.coverage import build_coverage
from job_indexer.db import (
    connect,
    create_fetch_run,
    finish_fetch_run,
    init_db,
    upsert_source_instance,
)
from job_indexer.models import SourceConfig


MATRIX = Path(__file__).resolve().parents[1] / "docs" / "platform_matrix.csv"
SOURCE = SourceConfig(
    name="workday-salesforce",
    platform="workday",
    tenant="salesforce",
    company="Salesforce",
    options={"host": "salesforce.wd12.myworkdayjobs.com", "site": "External_Career_Site"},
)


def test_partial_live_evidence_does_not_downgrade_matrix_status(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    create_fetch_run(
        conn,
        run_id="run-1",
        source=SOURCE,
        started_at="2026-11-10T00:00:00+00:00",
    )
    finish_fetch_run(
        conn,
        run_id="run-1",
        completed_at="2026-11-10T00:00:01+00:00",
        status="PARTIAL_SUCCESS",
        jobs_discovered=5,
        jobs_processed=5,
        jobs_inserted=5,
        jobs_updated=0,
        error_details="max_jobs_reached",
        duration_ms=1000,
        raw_payload_path=None,
        pagination={"complete": False, "limit_reason": "max_jobs_reached"},
    )

    coverage = build_coverage(conn, matrix_path=MATRIX)
    workday = next(
        platform for platform in coverage["platforms"] if platform["platform"] == "Workday"
    )

    assert workday["matrix_status"] == "LIVE_TESTED_MULTI_TENANT"
    assert workday["implementation_status"] == "LIVE_TESTED_MULTI_TENANT"
    assert workday["evidenced_sources"] == 1
    assert coverage["status_counts"]["LIVE_TESTED_MULTI_TENANT"] == 11
    conn.close()
