from __future__ import annotations

from pathlib import Path

from job_indexer.db import (
    connect,
    get_canonical_job,
    init_db,
    search_jobs,
    upsert_jobs,
    upsert_source_instance,
)
from job_indexer.models import JobListing, SourceConfig


def source(name: str, platform: str, company: str) -> SourceConfig:
    return SourceConfig(
        name=name,
        platform=platform,
        tenant=name,
        company=company,
    )


def job(
    *,
    platform: str,
    source_instance: str,
    external_id: str,
    title: str = "Software Engineer",
    company: str = "Acme",
    location: str | None = "Remote",
    description: str | None = "<p>Build distributed systems with Python and Go.</p>",
    source_url: str | None = None,
    application_url: str | None = None,
) -> JobListing:
    return JobListing(
        platform=platform,
        source_instance=source_instance,
        external_job_id=external_id,
        title=title,
        company=company,
        description=description,
        location=location,
        source_url=source_url or f"https://{platform}.example/{source_instance}/{external_id}",
        application_url=application_url,
        salary=None,
        employment_type="Full-time",
        remote_status="remote" if location and "remote" in location.lower() else "unknown",
        original_posted_at=None,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_checked_at="2026-01-01T00:00:00+00:00",
    )


def test_same_job_across_two_platforms_shares_canonical_job(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    gh = source("greenhouse-acme", "greenhouse", "Acme")
    lv = source("lever-acme", "lever", "Acme")
    upsert_source_instance(conn, gh)
    upsert_source_instance(conn, lv)

    upsert_jobs(conn, [job(platform="greenhouse", source_instance=gh.name, external_id="1")])
    upsert_jobs(conn, [job(platform="lever", source_instance=lv.name, external_id="abc")])

    results, total = search_jobs(conn)
    assert total == 1
    detail = get_canonical_job(conn, results[0]["id"])
    assert detail is not None
    assert {item["platform"] for item in detail["sources"]} == {"greenhouse", "lever"}


def test_same_title_different_company_stays_separate(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    a = source("greenhouse-acme", "greenhouse", "Acme")
    b = source("lever-beta", "lever", "Beta")
    upsert_source_instance(conn, a)
    upsert_source_instance(conn, b)

    upsert_jobs(conn, [job(platform="greenhouse", source_instance=a.name, external_id="1")])
    upsert_jobs(
        conn,
        [job(platform="lever", source_instance=b.name, external_id="1", company="Beta")],
    )

    results, total = search_jobs(conn)
    assert total == 2


def test_same_company_title_different_location_stays_separate(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    a = source("greenhouse-acme", "greenhouse", "Acme")
    b = source("lever-acme", "lever", "Acme")
    upsert_source_instance(conn, a)
    upsert_source_instance(conn, b)

    upsert_jobs(
        conn,
        [job(platform="greenhouse", source_instance=a.name, external_id="1", location="Remote")],
    )
    upsert_jobs(
        conn,
        [job(platform="lever", source_instance=b.name, external_id="1", location="London")],
    )

    results, total = search_jobs(conn)
    assert total == 2


def test_missing_description_does_not_block_exact_key_match(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    a = source("greenhouse-acme", "greenhouse", "Acme")
    b = source("lever-acme", "lever", "Acme")
    upsert_source_instance(conn, a)
    upsert_source_instance(conn, b)

    upsert_jobs(
        conn,
        [
            job(
                platform="greenhouse",
                source_instance=a.name,
                external_id="1",
                description=None,
            )
        ],
    )
    upsert_jobs(conn, [job(platform="lever", source_instance=b.name, external_id="1")])

    results, total = search_jobs(conn)
    assert total == 1
    assert results[0]["source_count"] == 2


def test_very_different_descriptions_stay_separate(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    a = source("greenhouse-acme", "greenhouse", "Acme")
    b = source("lever-acme", "lever", "Acme")
    upsert_source_instance(conn, a)
    upsert_source_instance(conn, b)

    upsert_jobs(
        conn,
        [
            job(
                platform="greenhouse",
                source_instance=a.name,
                external_id="1",
                description="<p>Python backend infrastructure security.</p>",
            )
        ],
    )
    upsert_jobs(
        conn,
        [
            job(
                platform="lever",
                source_instance=b.name,
                external_id="1",
                description="<p>Sales account executive quota territory.</p>",
            )
        ],
    )

    results, total = search_jobs(conn)
    assert total == 2


def test_exact_application_url_links_cross_source(tmp_path: Path) -> None:
    conn = connect(tmp_path / "jobs.db")
    init_db(conn)
    a = source("greenhouse-acme", "greenhouse", "Acme")
    b = source("lever-beta", "lever", "Beta")
    upsert_source_instance(conn, a)
    upsert_source_instance(conn, b)
    apply_url = "https://apply.example/acme/123"

    upsert_jobs(
        conn,
        [
            job(
                platform="greenhouse",
                source_instance=a.name,
                external_id="1",
                application_url=apply_url,
            )
        ],
    )
    upsert_jobs(
        conn,
        [
            job(
                platform="lever",
                source_instance=b.name,
                external_id="2",
                company="Beta",
                title="Different title",
                application_url=apply_url,
            )
        ],
    )

    results, total = search_jobs(conn)
    assert total == 1
    assert results[0]["source_count"] == 2
