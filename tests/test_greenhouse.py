from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.greenhouse import GreenhouseConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_stripe.json"
SOURCE = SourceConfig(
    name="greenhouse-stripe",
    platform="greenhouse",
    tenant="stripe",
    company="Stripe",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(payload: dict) -> GreenhouseConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GreenhouseConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_jobs_and_metadata() -> None:
    payload = load_fixture()
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == payload["meta"]["total"]
    assert batch.pagination["returned"] == 2
    assert batch.request_urls[0].startswith("https://boards-api.greenhouse.io/")
    assert "stripe" in batch.request_urls[0]
    assert batch.source_url == "https://boards.greenhouse.io/stripe"


def test_normalize_preserves_required_fields() -> None:
    raw_job = load_fixture()["jobs"][0]
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "greenhouse"
    assert job.source_instance == "greenhouse-stripe"
    assert job.external_job_id == str(raw_job["id"])
    assert job.title == raw_job["title"]
    assert job.company == "Stripe"
    assert job.description is not None
    assert job.description.startswith("<h2>")
    assert job.location == raw_job["location"]["name"]
    assert job.source_url == raw_job["absolute_url"]
    assert job.application_url is None
    assert job.original_posted_at == raw_job["first_published"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"
    assert job.last_checked_at == job.first_seen_at
    assert job.remote_status in {"remote", "hybrid", "onsite", "unknown"}


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()["jobs"][0])
    raw_job.pop("content", None)
    raw_job.pop("location", None)
    raw_job.pop("first_published", None)
    connector = make_connector({"jobs": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.location is None
    assert job.original_posted_at is None
    assert job.source_url == raw_job["absolute_url"]


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector = make_connector({"jobs": [], "meta": {"total": 0}})

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
    raw_job.pop("title")
    connector = make_connector({"jobs": []})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
