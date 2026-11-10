from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.ashby import AshbyConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "ashby_ashby.json"
SOURCE = SourceConfig(
    name="ashby-ashby",
    platform="ashby",
    tenant="ashby",
    company="Ashby",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(payload: dict) -> AshbyConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AshbyConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_jobs_and_metadata() -> None:
    payload = load_fixture()
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.pagination["returned"] == 2
    assert "api.ashbyhq.com" in batch.request_urls[0]
    assert "ashby" in batch.request_urls[0]
    assert batch.source_url == "https://jobs.ashbyhq.com/ashby"


def test_normalize_preserves_required_fields() -> None:
    raw_job = load_fixture()["jobs"][0]
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "ashby"
    assert job.source_instance == "ashby-ashby"
    assert job.external_job_id == raw_job["id"]
    assert job.title == raw_job["title"]
    assert job.company == "Ashby"
    assert job.description is not None
    assert job.description.startswith("<")
    assert job.location == raw_job["location"]
    assert job.source_url == raw_job["jobUrl"]
    assert job.application_url == raw_job["applyUrl"]
    assert job.salary == "€150K - €250K"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == raw_job["publishedAt"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"
    assert job.last_checked_at == job.first_seen_at


def test_normalize_uses_is_remote_when_workplace_type_is_missing() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    raw_job.pop("workplaceType", None)
    raw_job["isRemote"] = True
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.remote_status == "remote"


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    for key in (
        "applyUrl",
        "compensation",
        "descriptionHtml",
        "descriptionPlain",
        "employmentType",
        "isRemote",
        "location",
        "publishedAt",
        "workplaceType",
    ):
        raw_job.pop(key, None)
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.application_url is None
    assert job.salary is None
    assert job.description is None
    assert job.employment_type is None
    assert job.location is None
    assert job.remote_status == "unknown"
    assert job.original_posted_at is None
    assert job.source_url == raw_job["jobUrl"]


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector = make_connector({"jobs": [], "apiVersion": "1"})

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0


def test_invalid_top_level_structure_is_rejected() -> None:
    connector = make_connector({"jobs": "not-a-list"})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_job_missing_required_field_is_rejected() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    raw_job.pop("jobUrl")
    connector = make_connector({"jobs": []})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
