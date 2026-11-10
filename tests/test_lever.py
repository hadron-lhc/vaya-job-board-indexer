from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.lever import LeverConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "lever_palantir.json"
SOURCE = SourceConfig(
    name="lever-palantir",
    platform="lever",
    tenant="palantir",
    company="Palantir",
    options={"api_host": "api.lever.co", "page_size": 100},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(pages: list[list[dict] | int], source: SourceConfig = SOURCE) -> tuple[LeverConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        skip = int(request.url.params.get("skip", "0"))
        if skip >= len(pages):
            return httpx.Response(200, json=[], request=request)
        page = pages[skip]
        if isinstance(page, int):
            return httpx.Response(page, text="upstream error", request=request)
        return httpx.Response(200, json=page, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LeverConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_reads_jobs_and_pagination_metadata() -> None:
    fixture = load_fixture()
    connector, calls = make_connector([fixture])

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 1
    assert batch.pagination["returned"] == 2
    assert len(calls) == 1
    assert "palantir" in batch.request_urls[0]
    assert batch.source_url == "https://jobs.lever.co/palantir"


def test_normalize_preserves_source_and_application_urls() -> None:
    raw_job = load_fixture()[0]
    connector, _ = make_connector([[]])

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "lever"
    assert job.source_instance == "lever-palantir"
    assert job.external_job_id == raw_job["id"]
    assert job.title == raw_job["text"]
    assert job.company == "Palantir"
    assert job.location == raw_job["categories"]["location"]
    assert job.description is not None
    assert job.source_url == raw_job["hostedUrl"]
    assert job.application_url == raw_job["applyUrl"]
    assert job.employment_type == raw_job["categories"]["commitment"]
    assert job.original_posted_at is not None
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"
    assert job.last_checked_at == job.first_seen_at
    assert job.remote_status in {"remote", "hybrid", "onsite", "unknown"}


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()[0])
    raw_job.pop("applyUrl", None)
    raw_job.pop("categories", None)
    raw_job.pop("description", None)
    raw_job.pop("descriptionPlain", None)
    raw_job.pop("salaryRange", None)
    raw_job.pop("workplaceType", None)
    raw_job.pop("createdAt", None)
    connector, _ = make_connector([[]])

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.application_url is None
    assert job.description is None
    assert job.salary is None
    assert job.employment_type is None
    assert job.remote_status == "unknown"
    assert job.original_posted_at is None
    assert job.source_url == raw_job["hostedUrl"]


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector, _ = make_connector([[]])

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["returned"] == 0


def test_invalid_top_level_structure_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = LeverConnector(HttpClient(client=client, max_retries=0))

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_pagination_uses_skip_and_limit() -> None:
    fixture = load_fixture()
    source = SourceConfig(
        name="lever-palantir",
        platform="lever",
        tenant="palantir",
        company="Palantir",
        options={"api_host": "api.lever.co", "page_size": 1},
    )
    connector, calls = make_connector([fixture[:1], fixture[1:2], []], source)

    batch = connector.fetch(source)

    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 3
    assert len(calls) == 3
    assert "skip=0" in calls[0]
    assert "skip=1" in calls[1]
    assert "skip=2" in calls[2]


def test_partial_fetch_returns_jobs_fetched_before_failure() -> None:
    fixture = load_fixture()
    source = SourceConfig(
        name="lever-palantir",
        platform="lever",
        tenant="palantir",
        company="Palantir",
        options={"api_host": "api.lever.co", "page_size": 1},
    )
    connector, _ = make_connector([fixture[:1], 500], source)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert len(batch.request_urls) == 1


def test_partial_fetch_preserves_jobs_when_later_page_is_invalid_json() -> None:
    fixture = load_fixture()
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
        return httpx.Response(200, text="not-json", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = LeverConnector(HttpClient(client=client, max_retries=0))

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert len(batch.request_urls) == 1


def test_invalid_api_host_is_rejected() -> None:
    source = SourceConfig(
        name="lever-palantir",
        platform="lever",
        tenant="palantir",
        company="Palantir",
        options={"api_host": "example.com"},
    )
    connector, _ = make_connector([[]], source)

    with pytest.raises(ValueError):
        connector.fetch(source)
