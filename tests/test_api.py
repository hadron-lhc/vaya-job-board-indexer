from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from job_indexer.api import create_server
from job_indexer.db import connect, init_db, upsert_jobs, upsert_source_instance
from job_indexer.models import JobListing, SourceConfig


@pytest.fixture
def api_server(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    conn = connect(db_path)
    init_db(conn)
    source = SourceConfig(
        name="greenhouse-acme",
        platform="greenhouse",
        tenant="acme",
        company="Acme",
    )
    upsert_source_instance(conn, source)
    upsert_jobs(
        conn,
        [
            JobListing(
                platform="greenhouse",
                source_instance=source.name,
                external_job_id="1",
                title="Senior Python Engineer",
                company="Acme",
                description="<p>Build reliable distributed systems.</p>",
                location="Remote",
                source_url="https://example.test/jobs/1",
                application_url="https://example.test/apply/1",
                salary=None,
                employment_type="Full-time",
                remote_status="remote",
                original_posted_at=None,
                first_seen_at="2026-01-01T00:00:00+00:00",
                last_checked_at="2026-01-01T00:00:00+00:00",
            ),
            JobListing(
                platform="greenhouse",
                source_instance=source.name,
                external_job_id="2",
                title="Account Executive",
                company="Acme",
                description="<p>Sell software.</p>",
                location="London",
                source_url="https://example.test/jobs/2",
                application_url=None,
                salary=None,
                employment_type="Full-time",
                remote_status="onsite",
                original_posted_at=None,
                first_seen_at="2026-01-01T00:00:00+00:00",
                last_checked_at="2026-01-01T00:00:00+00:00",
            ),
        ],
    )
    conn.close()

    server = create_server(db_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get_json(url: str) -> tuple[int, dict]:
    with urlopen(url) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> tuple[int, str]:
    with urlopen(url) as response:
        return response.status, response.read().decode("utf-8")


def test_health_and_jobs_search(api_server: str) -> None:
    status, health = get_json(f"{api_server}/health")
    assert status == 200
    assert health["status"] == "ok"
    assert health["jobs"] == 2

    status, payload = get_json(f"{api_server}/api/v1/jobs?q=python")
    assert status == 200
    assert payload["total"] == 1
    assert payload["items"][0]["normalized_title"] == "senior-python-engineer"


def test_company_and_location_filters(api_server: str) -> None:
    _, payload = get_json(f"{api_server}/api/v1/jobs?company=acme")
    assert payload["total"] == 2
    _, payload = get_json(f"{api_server}/api/v1/jobs?location=london")
    assert payload["total"] == 1
    _, payload = get_json(f"{api_server}/api/v1/jobs?platform=greenhouse")
    assert payload["total"] == 2


def test_job_detail_includes_source_links(api_server: str) -> None:
    _, payload = get_json(f"{api_server}/api/v1/jobs?q=python")
    job_id = payload["items"][0]["id"]
    status, detail = get_json(f"{api_server}/api/v1/jobs/{job_id}")
    assert status == 200
    assert detail["sources"][0]["source_url"] == "https://example.test/jobs/1"
    assert detail["sources"][0]["application_url"] == "https://example.test/apply/1"


def test_sources_coverage_and_fetch_runs(api_server: str) -> None:
    _, sources = get_json(f"{api_server}/api/v1/sources")
    assert sources["items"][0]["name"] == "greenhouse-acme"
    assert sources["items"][0]["job_count"] == 2

    _, coverage = get_json(f"{api_server}/api/v1/coverage")
    assert coverage["total_required"] == 78
    assert coverage["categories"] == {"ATS": 58, "Job Board": 20}
    assert coverage["source_instances"] == 1
    assert coverage["total_jobs"] == 2

    _, runs = get_json(f"{api_server}/api/v1/fetch-runs")
    assert runs["items"] == []


def test_ui_renders_jobs_and_coverage(api_server: str) -> None:
    status, page = get_text(f"{api_server}/?q=python")
    assert status == 200
    assert "Senior Python Engineer" in page
    assert "Apply" in page

    status, page = get_text(f"{api_server}/coverage")
    assert status == 200
    assert "Required platforms: 78" in page


def test_invalid_parameters_and_missing_job(api_server: str) -> None:
    with pytest.raises(HTTPError) as exc_info:
        get_json(f"{api_server}/api/v1/jobs?sort=bad")
    assert exc_info.value.code == 400

    with pytest.raises(HTTPError) as exc_info:
        get_json(f"{api_server}/api/v1/jobs?limit=1000")
    assert exc_info.value.code == 400

    with pytest.raises(HTTPError) as exc_info:
        get_json(f"{api_server}/api/v1/jobs/does-not-exist")
    assert exc_info.value.code == 404
