from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.recruitee import RecruiteeConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "recruitee_bunq.json"
SOURCE = SourceConfig(
    name="recruitee-bunq",
    platform="recruitee",
    tenant="bunq",
    company="bunq",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(payload: dict) -> RecruiteeConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return RecruiteeConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_offers_and_metadata() -> None:
    payload = load_fixture()
    connector = make_connector(payload)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.pagination["returned"] == 2
    assert batch.request_urls == ["https://bunq.recruitee.com/api/offers/"]
    assert batch.source_url == "https://bunq.recruitee.com/"


def test_normalize_preserves_required_fields() -> None:
    raw_job = load_fixture()["offers"][0]
    connector = make_connector({"offers": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "recruitee"
    assert job.source_instance == "recruitee-bunq"
    assert job.external_job_id == str(raw_job["id"])
    assert job.title == raw_job["title"]
    assert job.company == "bunq"
    assert job.description is not None
    assert "<p" in job.description
    assert job.location == "Paris"
    assert job.source_url == raw_job["careers_url"]
    assert job.application_url == raw_job["careers_apply_url"]
    assert job.salary is None
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == "2026-11-10T07:45:05+00:00"
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(load_fixture()["offers"][0])
    for key in (
        "careers_apply_url",
        "careers_url",
        "company_name",
        "description",
        "employment_type_code",
        "locations",
        "location",
        "remote",
        "hybrid",
        "on_site",
        "published_at",
        "requirements",
        "salary",
        "slug",
    ):
        raw_job.pop(key, None)
    connector = make_connector({"offers": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.application_url is None
    assert job.company == "bunq"
    assert job.description is None
    assert job.employment_type is None
    assert job.location is None
    assert job.original_posted_at is None
    assert job.source_url == f"https://bunq.recruitee.com/o/{raw_job['id']}"


def test_normalize_formats_salary() -> None:
    raw_job = dict(load_fixture()["offers"][0])
    raw_job["salary"] = {"min": "50000", "max": "70000", "currency": "EUR", "period": "year"}
    connector = make_connector({"offers": []})

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.salary == "50000-70000 EUR year"


def test_empty_response_is_a_successful_empty_batch() -> None:
    connector = make_connector({"offers": []})

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0


def test_invalid_top_level_structure_is_rejected() -> None:
    connector = make_connector({"offers": "not-a-list"})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_offer_missing_id_or_title_is_rejected() -> None:
    raw_job = dict(load_fixture()["offers"][0])
    raw_job.pop("id")
    connector = make_connector({"offers": []})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
