from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.workable import WorkableConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "workable_huggingface.json"
SOURCE = SourceConfig(
    name="workable-huggingface",
    platform="workable",
    tenant="huggingface",
    company="Hugging Face",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(payload: dict) -> WorkableConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WorkableConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_jobs_and_metadata() -> None:
    payload = load_fixture()
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.pagination["returned"] == 2
    assert "apply.workable.com" in batch.request_urls[0]
    assert "details=true" in batch.request_urls[0]
    assert batch.source_url == "https://apply.workable.com/huggingface"


def test_normalize_preserves_required_fields() -> None:
    raw_job = load_fixture()["jobs"][0]
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "workable"
    assert job.source_instance == "workable-huggingface"
    assert job.external_job_id == raw_job["shortcode"]
    assert job.title == raw_job["title"]
    assert job.company == "Hugging Face"
    assert job.description is not None
    assert job.description.startswith("<")
    assert job.location == "Paris, Île-de-France, France"
    assert job.source_url == raw_job["url"]
    assert job.application_url == raw_job["application_url"]
    assert job.salary is None
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == raw_job["published_on"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"
    assert job.last_checked_at == job.first_seen_at


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    for key in (
        "application_url",
        "city",
        "country",
        "created_at",
        "description",
        "employment_type",
        "locations",
        "published_on",
        "state",
        "telecommuting",
    ):
        raw_job.pop(key, None)
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.application_url is None
    assert job.description is None
    assert job.employment_type is None
    assert job.location is None
    assert job.remote_status == "unknown"
    assert job.original_posted_at is None
    assert job.source_url == raw_job["url"]


def test_fetch_merges_duplicate_shortcodes_and_locations() -> None:
    payload = load_fixture()
    first = dict(payload["jobs"][0])
    second = dict(first)
    second["locations"] = [
        {"city": "Berlin", "region": "", "country": "Germany"}
    ]
    payload = {"name": payload["name"], "jobs": [first, second]}
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert len(batch.raw_jobs) == 1
    assert batch.pagination["total"] == 2
    assert batch.pagination["returned"] == 1
    assert batch.pagination["duplicate_postings"] == 1
    job = connector.normalize(batch.raw_jobs[0], SOURCE, CHECKED_AT)
    assert job.location == "Paris, Île-de-France, France; Berlin, Germany"


def test_normalize_formats_multiple_locations() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    raw_job["locations"] = [
        {"city": "Paris", "region": "Île-de-France", "country": "France"},
        {"city": "Berlin", "region": "", "country": "Germany"},
    ]
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.location == "Paris, Île-de-France, France; Berlin, Germany"


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector = make_connector({"name": "Hugging Face", "jobs": []})

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
    raw_job.pop("shortcode")
    connector = make_connector({"jobs": []})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
