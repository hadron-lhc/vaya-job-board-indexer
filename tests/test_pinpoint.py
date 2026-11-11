from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.pinpoint import PinpointConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "pinpoint_avaaz.json"
SOURCE = SourceConfig(
    name="pinpoint-avaaz",
    platform="pinpoint",
    tenant="avaaz",
    company="Avaaz",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(payload: dict) -> PinpointConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PinpointConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_postings_and_metadata() -> None:
    payload = load_fixture()
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.request_urls == ["https://avaaz.pinpointhq.com/postings.json"]
    assert batch.source_url == "https://avaaz.pinpointhq.com/"


def test_normalize_preserves_required_fields() -> None:
    raw_job = load_fixture()["data"][0]
    connector = make_connector({"data": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "pinpoint"
    assert job.source_instance == "pinpoint-avaaz"
    assert job.external_job_id == "20b6e944-fe3b-488f-b811-3c4714a433eb"
    assert job.title == raw_job["title"]
    assert job.company == "Avaaz"
    assert job.description is not None
    assert "Position overview" in job.description
    assert job.location == "Remote"
    assert job.source_url == raw_job["url"]
    assert job.application_url == raw_job["url"]
    assert job.salary == "€4,000 - €5,000 / month"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "hybrid"
    assert job.original_posted_at is None
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()["data"][0])
    for key in (
        "benefits",
        "compensation",
        "compensation_visible",
        "description",
        "employment_type",
        "employment_type_text",
        "key_responsibilities",
        "location",
        "skills_knowledge_expertise",
        "workplace_type",
        "workplace_type_text",
    ):
        raw_job.pop(key, None)
    connector = make_connector({"data": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.employment_type is None
    assert job.location is None
    assert job.remote_status == "unknown"
    assert job.salary is None


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector = make_connector({"data": []})

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0


def test_invalid_top_level_structure_is_rejected() -> None:
    connector = make_connector({"data": "not-a-list"})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_posting_missing_title_or_url_is_rejected() -> None:
    raw_job = dict(load_fixture()["data"][0])
    raw_job.pop("url")
    connector = make_connector({"data": []})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
