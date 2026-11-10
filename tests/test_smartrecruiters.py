from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from job_indexer.connectors.smartrecruiters import SmartRecruitersConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "smartrecruiters_canva.json"
SOURCE = SourceConfig(
    name="smartrecruiters-canva",
    platform="smartrecruiters",
    tenant="Canva",
    company="Canva",
    options={"page_size": 100},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(
    fixture: dict,
    *,
    page_size: int = 100,
    fail_list_offset: int | None = None,
    fail_detail_at: str | None = None,
    invalid_detail_at: str | None = None,
) -> tuple[SmartRecruitersConnector, list[str]]:
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"page_size": page_size},
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        path = request.url.path
        if path.endswith("/postings"):
            offset = int(request.url.params.get("offset", "0"))
            limit = int(request.url.params.get("limit", "100"))
            if fail_list_offset is not None and offset == fail_list_offset:
                return httpx.Response(500, text="upstream error", request=request)
            content = fixture["list"]["content"][offset : offset + limit]
            return httpx.Response(
                200,
                json={
                    "offset": offset,
                    "limit": limit,
                    "totalFound": fixture["list"]["totalFound"],
                    "content": content,
                },
                request=request,
            )

        job_id = path.rstrip("/").rsplit("/", 1)[-1]
        if fail_detail_at is not None and job_id == fail_detail_at:
            return httpx.Response(500, text="upstream error", request=request)
        if invalid_detail_at is not None and job_id == invalid_detail_at:
            return httpx.Response(200, text="not-json", request=request)
        return httpx.Response(200, json=fixture["details"][job_id], request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        SmartRecruitersConnector(HttpClient(client=client, max_retries=0)),
        calls,
    )


def source_with_page_size(page_size: int) -> SourceConfig:
    return SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"page_size": page_size},
    )


def first_detail(fixture: dict) -> dict[str, Any]:
    return next(iter(fixture["details"].values()))


def test_fetch_paginates_and_fetches_details() -> None:
    fixture = load_fixture()
    connector, calls = make_connector(fixture)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 1
    assert batch.pagination["total"] == 2
    assert batch.pagination["returned"] == 2
    assert batch.pagination["detail_requests"] == 2
    assert batch.pagination["detail_failures"] == 0
    assert len(calls) == 3
    assert len(batch.request_urls) == 3
    assert len(batch.raw_payloads) == 3
    assert "api.smartrecruiters.com" in calls[0]
    assert "limit=100" in calls[0]
    assert batch.source_url == "https://jobs.smartrecruiters.com/Canva"


def test_pagination_uses_offset_and_limit() -> None:
    fixture = load_fixture()
    connector, calls = make_connector(fixture, page_size=1)

    batch = connector.fetch(source_with_page_size(1))

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 2
    assert batch.pagination["detail_requests"] == 2
    assert len(calls) == 4
    assert "offset=0" in calls[0]
    assert "offset=1" in calls[1]


def test_normalize_preserves_required_fields() -> None:
    fixture = load_fixture()
    raw_job = first_detail(fixture)
    connector, _ = make_connector(fixture)

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "smartrecruiters"
    assert job.source_instance == "smartrecruiters-canva"
    assert job.external_job_id == raw_job["id"]
    assert job.title == raw_job["name"]
    assert job.company == "Canva"
    assert job.description is not None
    assert "Job Description" in job.description
    assert job.location == raw_job["location"]["fullLocation"]
    assert job.source_url == raw_job["postingUrl"]
    assert job.application_url == raw_job["applyUrl"]
    assert job.employment_type == "Full-time"
    assert job.remote_status in {"remote", "hybrid", "onsite", "unknown"}
    assert job.original_posted_at == raw_job["releasedDate"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"
    assert job.last_checked_at == job.first_seen_at


def test_normalize_falls_back_to_public_url_for_list_only_posting() -> None:
    fixture = load_fixture()
    raw_job = dict(fixture["list"]["content"][0])
    connector, _ = make_connector(fixture)

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.application_url is None
    assert job.source_url == (
        f"https://jobs.smartrecruiters.com/Canva/{raw_job['id']}"
    )


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(first_detail(load_fixture()))
    for key in (
        "applyUrl",
        "company",
        "compensation",
        "jobAd",
        "location",
        "postingUrl",
        "releasedDate",
        "typeOfEmployment",
    ):
        raw_job.pop(key, None)
    connector, _ = make_connector(load_fixture())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.application_url is None
    assert job.company == "Canva"
    assert job.description is None
    assert job.location is None
    assert job.remote_status == "unknown"
    assert job.original_posted_at is None
    assert job.source_url == (
        f"https://jobs.smartrecruiters.com/Canva/{raw_job['id']}"
    )


def test_empty_response_is_a_successful_empty_batch() -> None:
    fixture = {"list": {"totalFound": 0, "content": []}, "details": {}}
    connector, calls = make_connector(fixture)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0
    assert batch.pagination["detail_requests"] == 0
    assert len(calls) == 1


def test_invalid_top_level_structure_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "valid"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = SmartRecruitersConnector(HttpClient(client=client, max_retries=0))

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_posting_without_id_is_rejected() -> None:
    fixture = {
        "list": {"totalFound": 1, "content": [{"name": "Missing id"}]},
        "details": {},
    }
    connector, _ = make_connector(fixture)

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_detail_failure_returns_partial_batch_with_list_jobs() -> None:
    fixture = load_fixture()
    first_id = str(fixture["list"]["content"][0]["id"])
    connector, _ = make_connector(fixture, fail_detail_at=first_id)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(SOURCE)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["detail_requests"] == 0
    assert batch.pagination["detail_failures"] == 1
    assert batch.pagination["complete"] is False


def test_invalid_detail_json_returns_partial_batch() -> None:
    fixture = load_fixture()
    first_id = str(fixture["list"]["content"][0]["id"])
    connector, _ = make_connector(fixture, invalid_detail_at=first_id)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(SOURCE)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["detail_failures"] == 1


def test_list_failure_after_first_page_returns_partial_batch() -> None:
    fixture = load_fixture()
    connector, _ = make_connector(fixture, page_size=1, fail_list_offset=1)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source_with_page_size(1))

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["detail_requests"] == 0


def test_invalid_page_size_is_rejected() -> None:
    fixture = load_fixture()
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"page_size": 0},
    )
    connector, _ = make_connector(fixture, page_size=0)

    with pytest.raises(ValueError):
        connector.fetch(source)
