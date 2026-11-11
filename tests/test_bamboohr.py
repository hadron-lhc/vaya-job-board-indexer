from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.bamboohr import BambooHRConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = SourceConfig(
    name="bamboohr-acme",
    platform="bamboohr",
    tenant="acme",
    company="ACME",
    options={"max_jobs": 10},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_list() -> dict:
    return json.loads((FIXTURES / "bamboohr_list.json").read_text(encoding="utf-8"))


def load_detail() -> dict:
    return json.loads((FIXTURES / "bamboohr_detail.json").read_text(encoding="utf-8"))


def make_connector(listing: dict, detail: dict | None = None) -> tuple[BambooHRConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/careers/list":
            return httpx.Response(200, json=listing, request=request)
        return httpx.Response(200, json=detail or load_detail(), request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BambooHRConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_reads_list_and_details() -> None:
    connector, calls = make_connector(load_list())

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert calls[0] == "https://acme.bamboohr.com/careers/list"
    assert calls[1] == "https://acme.bamboohr.com/careers/35/detail"
    assert batch.source_url == "https://acme.bamboohr.com/careers"


def test_normalize_preserves_required_fields() -> None:
    connector, _ = make_connector(load_list())
    raw_job = connector.fetch(SOURCE).raw_jobs[0]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "bamboohr"
    assert job.external_job_id == "35"
    assert job.title == "Infrastructure Ops Engineer"
    assert job.company == "ACME"
    assert job.description == "<p>Run the platform.</p>"
    assert job.location == "Austin, Texas, United States"
    assert job.source_url == "https://acme.bamboohr.com/careers/35"
    assert job.application_url == job.source_url
    assert job.salary == "$150,000 - $180,000"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == "2026-03-14"


def test_normalize_falls_back_to_list_fields() -> None:
    connector, _ = make_connector(load_list())
    raw_job = dict(connector.fetch(SOURCE).raw_jobs[1])
    raw_job.pop("_detail")

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.location == "Austin, Texas"
    assert job.employment_type == "Full-time"
    assert job.original_posted_at is None


def test_max_jobs_returns_partial_batch() -> None:
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"max_jobs": 1},
    )
    connector, _ = make_connector(load_list())

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["limit_reason"] == "max_jobs_reached"


def test_invalid_list_shape_is_rejected() -> None:
    connector, _ = make_connector({"result": "not-a-list"})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_job_missing_required_fields_is_rejected() -> None:
    raw_job = dict(load_list()["result"][0])
    raw_job.pop("id")
    connector, _ = make_connector(load_list())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
