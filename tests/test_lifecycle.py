from __future__ import annotations

from pathlib import Path

from job_indexer.db import (
    apply_source_scan,
    connect,
    get_canonical_job,
    get_job_by_external_id,
    init_db,
    upsert_jobs,
    upsert_source_instance,
)
from job_indexer.models import JobListing, SourceConfig


SOURCE = SourceConfig(
    name="greenhouse-acme",
    platform="greenhouse",
    tenant="acme",
    company="Acme",
)


def make_job(
    *,
    external_job_id: str = "1",
    title: str = "Engineer",
    description: str | None = "<p>Build reliable systems</p>",
    checked_at: str = "2026-01-01T00:00:00+00:00",
) -> JobListing:
    return JobListing(
        platform="greenhouse",
        source_instance=SOURCE.name,
        external_job_id=external_job_id,
        title=title,
        company="Acme",
        description=description,
        location="Remote",
        source_url=f"https://example.test/jobs/{external_job_id}",
        application_url=None,
        salary=None,
        employment_type="Full-time",
        remote_status="remote",
        original_posted_at=None,
        first_seen_at=checked_at,
        last_checked_at=checked_at,
    )


def test_first_missing_scan_marks_missing_and_second_closes(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    upsert_jobs(conn, [make_job()])

    missing, closed = apply_source_scan(
        conn,
        source=SOURCE,
        seen_external_ids=[],
        checked_at="2026-01-02T00:00:00+00:00",
        complete=True,
    )
    assert (missing, closed) == (1, 0)
    stored = get_job_by_external_id(
        conn,
        platform=SOURCE.platform,
        source_instance=SOURCE.name,
        external_job_id="1",
    )
    assert stored is not None
    assert stored["source_status"] == "missing"
    assert stored["missing_scans"] == 1
    assert stored["closed_at"] is None
    assert get_canonical_job(conn, stored["canonical_job_id"])["status"] == "open"

    missing, closed = apply_source_scan(
        conn,
        source=SOURCE,
        seen_external_ids=[],
        checked_at="2026-01-03T00:00:00+00:00",
        complete=True,
    )
    assert (missing, closed) == (1, 1)
    stored = get_job_by_external_id(
        conn,
        platform=SOURCE.platform,
        source_instance=SOURCE.name,
        external_job_id="1",
    )
    assert stored is not None
    assert stored["source_status"] == "closed"
    assert stored["missing_scans"] == 2
    assert stored["closed_at"] == "2026-01-03T00:00:00+00:00"
    assert get_canonical_job(conn, stored["canonical_job_id"])["status"] == "closed"


def test_partial_or_failed_scan_never_changes_status(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    upsert_jobs(conn, [make_job()])

    assert apply_source_scan(
        conn,
        source=SOURCE,
        seen_external_ids=[],
        checked_at="2026-01-02T00:00:00+00:00",
        complete=False,
    ) == (0, 0)
    stored = get_job_by_external_id(
        conn,
        platform=SOURCE.platform,
        source_instance=SOURCE.name,
        external_job_id="1",
    )
    assert stored is not None
    assert stored["source_status"] == "open"
    assert stored["missing_scans"] == 0


def test_reappearing_job_resets_missing_state(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    upsert_jobs(conn, [make_job()])
    apply_source_scan(
        conn,
        source=SOURCE,
        seen_external_ids=[],
        checked_at="2026-01-02T00:00:00+00:00",
        complete=True,
    )
    upsert_jobs(conn, [make_job(checked_at="2026-01-03T00:00:00+00:00")])

    stored = get_job_by_external_id(
        conn,
        platform=SOURCE.platform,
        source_instance=SOURCE.name,
        external_job_id="1",
    )
    assert stored is not None
    assert stored["source_status"] == "open"
    assert stored["missing_scans"] == 0
    assert stored["last_missing_at"] is None
    assert stored["closed_at"] is None


def test_change_detection_preserves_first_seen_and_updates_last_changed(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    upsert_source_instance(conn, SOURCE)
    upsert_jobs(conn, [make_job(checked_at="2026-01-01T00:00:00+00:00")])

    inserted, updated, changed = upsert_jobs(
        conn,
        [make_job(title="Senior Engineer", checked_at="2026-01-02T00:00:00+00:00")],
    )
    assert (inserted, updated, changed) == (0, 1, 1)
    stored = get_job_by_external_id(
        conn,
        platform=SOURCE.platform,
        source_instance=SOURCE.name,
        external_job_id="1",
    )
    assert stored is not None
    assert stored["first_seen_at"] == "2026-01-01T00:00:00+00:00"
    assert stored["last_changed_at"] == stored["updated_at"]
    assert stored["last_changed_at"] != "2026-01-01T00:00:00+00:00"

    _, _, changed = upsert_jobs(
        conn,
        [make_job(title="Senior Engineer", checked_at="2026-01-03T00:00:00+00:00")],
    )
    assert changed == 0
