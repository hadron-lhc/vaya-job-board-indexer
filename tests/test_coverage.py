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
    assert coverage["status_counts"]["LIVE_TESTED_MULTI_TENANT"] == 15
    assert None not in coverage["live_multi_tenant_platforms"]
    assert "workday" in coverage["live_multi_tenant_platforms"]
    conn.close()


def test_coverage_checklist_includes_all_78_platforms_and_evidence(tmp_path: Path) -> None:
    from job_indexer.coverage import (
        build_coverage_checklist,
        render_coverage_checklist_markdown,
    )

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
    evidence_dir = tmp_path / "live_runs"
    evidence_dir.mkdir()
    (evidence_dir / "workday-salesforce.json").write_text("{}", encoding="utf-8")

    checklist = build_coverage_checklist(
        conn,
        matrix_path=MATRIX,
        evidence_dir=evidence_dir,
    )
    markdown = render_coverage_checklist_markdown(checklist)

    assert checklist["total_required"] == 78
    assert len(checklist["platforms"]) == 78
    workday = next(
        platform for platform in checklist["platforms"] if platform["platform"] == "Workday"
    )
    assert workday["coverage_state"] == "live_multi_tenant"
    assert workday["evidence_paths"] == [str(evidence_dir / "workday-salesforce.json")]
    assert "second_tenant" in workday["missing_requirements"]
    assert "| Workday | ATS | `LIVE_TESTED_MULTI_TENANT`" in markdown
    assert markdown.count("| ATS |") == 58
    assert markdown.count("| Job Board |") == 20
    conn.close()
