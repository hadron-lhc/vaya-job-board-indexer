from __future__ import annotations

import json
from pathlib import Path

import httpx

from job_indexer.connectors.greenhouse import GreenhouseConnector
from job_indexer.connectors.lever import LeverConnector
from job_indexer.db import connect, get_fetch_run, get_job_count, init_db
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig
from job_indexer.runner import run_fetch


FIXTURES = Path(__file__).parent / "fixtures"


def greenhouse_source() -> SourceConfig:
    return SourceConfig(
        name="greenhouse-stripe",
        platform="greenhouse",
        tenant="stripe",
        company="Stripe",
    )


def greenhouse_connector(payload: dict, status_code: int = 200) -> GreenhouseConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GreenhouseConnector(HttpClient(client=client, max_retries=0))


def test_successful_fetch_persists_jobs_and_is_idempotent(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "greenhouse_stripe.json").read_text(encoding="utf-8"))
    source = greenhouse_source()
    connector = greenhouse_connector(payload)
    db_path = tmp_path / "jobs.db"
    artifacts_dir = tmp_path / "artifacts"

    first = run_fetch(source, connector, db_path=db_path, artifacts_dir=artifacts_dir)

    assert first.status == "success"
    assert first.jobs_discovered == 2
    assert first.jobs_processed == 2
    assert first.jobs_inserted == 2
    assert first.jobs_updated == 0
    assert first.raw_payload_path is not None
    assert Path(first.raw_payload_path).exists()

    conn = connect(db_path)
    init_db(conn)
    assert get_job_count(conn, source.name) == 2
    run = get_fetch_run(conn, first.run_id)
    assert run is not None
    assert run["status"] == "success"
    conn.close()

    second = run_fetch(source, connector, db_path=db_path, artifacts_dir=artifacts_dir)

    assert second.status == "success"
    assert second.jobs_inserted == 0
    assert second.jobs_updated == 2
    conn = connect(db_path)
    init_db(conn)
    assert get_job_count(conn, source.name) == 2
    conn.close()


def test_failed_fetch_is_recorded_and_does_not_create_jobs(tmp_path: Path) -> None:
    source = greenhouse_source()
    connector = greenhouse_connector({"jobs": []}, status_code=500)
    db_path = tmp_path / "jobs.db"

    result = run_fetch(source, connector, db_path=db_path, artifacts_dir=tmp_path / "artifacts")

    assert result.status == "failed"
    assert result.jobs_discovered == 0
    assert result.jobs_processed == 0
    assert result.error is not None
    assert "HTTP 500" in result.error

    conn = connect(db_path)
    init_db(conn)
    assert get_job_count(conn, source.name) == 0
    run = get_fetch_run(conn, result.run_id)
    assert run is not None
    assert run["status"] == "failed"
    assert "HTTP 500" in run["error_details"]
    conn.close()


def test_normalization_failure_is_recorded_as_failed(tmp_path: Path) -> None:
    source = greenhouse_source()
    connector = greenhouse_connector(
        {"jobs": [{"id": 1, "absolute_url": "https://example.test/jobs/1"}]}
    )
    db_path = tmp_path / "jobs.db"

    result = run_fetch(source, connector, db_path=db_path, artifacts_dir=tmp_path / "artifacts")

    assert result.status == "failed"
    assert result.jobs_discovered == 1
    assert result.jobs_processed == 0
    assert result.error is not None
    assert "InvalidResponseError" in result.error

    conn = connect(db_path)
    init_db(conn)
    assert get_job_count(conn, source.name) == 0
    run = get_fetch_run(conn, result.run_id)
    assert run is not None
    assert run["status"] == "failed"
    conn.close()


def test_partial_fetch_persists_jobs_and_records_partial_status(tmp_path: Path) -> None:
    fixture = json.loads((FIXTURES / "lever_palantir.json").read_text(encoding="utf-8"))
    source = SourceConfig(
        name="lever-palantir",
        platform="lever",
        tenant="palantir",
        company="Palantir",
        options={"api_host": "api.lever.co", "page_size": 1},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params.get("skip", "0"))
        if skip == 0:
            return httpx.Response(200, json=fixture[:1], request=request)
        return httpx.Response(500, text="upstream error", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = LeverConnector(HttpClient(client=client, max_retries=0))
    db_path = tmp_path / "jobs.db"

    result = run_fetch(source, connector, db_path=db_path, artifacts_dir=tmp_path / "artifacts")

    assert result.status == "partial"
    assert result.jobs_discovered == 1
    assert result.jobs_processed == 1
    assert result.jobs_inserted == 1
    assert result.error is not None
    assert "HTTP 500" in result.error

    conn = connect(db_path)
    init_db(conn)
    assert get_job_count(conn, source.name) == 1
    run = get_fetch_run(conn, result.run_id)
    assert run is not None
    assert run["status"] == "partial"
    conn.close()
