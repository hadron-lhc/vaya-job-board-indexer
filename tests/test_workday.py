from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.workday import WorkdayConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "workday_salesforce.json"
SOURCE = SourceConfig(
    name="workday-salesforce",
    platform="workday",
    tenant="salesforce",
    company="Salesforce",
    options={"host": "salesforce.wd12.myworkdayjobs.com", "site": "External_Career_Site"},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(
    fixture: dict,
    *,
    fail_detail_at: str | None = None,
) -> tuple[WorkdayConnector, list[tuple[str, str]]]:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and path.endswith("/jobs"):
            listing = fixture["list"]
            return httpx.Response(
                200,
                json={"total": listing["total"], "jobPostings": listing["jobPostings"]},
                request=request,
            )
        external_path = "/" + path.split("/External_Career_Site/", 1)[1]
        if fail_detail_at is not None and external_path == fail_detail_at:
            return httpx.Response(500, text="upstream error", request=request)
        return httpx.Response(200, json=fixture["details"][external_path], request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WorkdayConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_posts_for_list_and_gets_details() -> None:
    fixture = load_fixture()
    connector, calls = make_connector(fixture)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 1
    assert batch.pagination["total_items"] == 2
    assert calls[0][0] == "POST"
    assert calls[0][1] == (
        "https://salesforce.wd12.myworkdayjobs.com/wday/cxs/"
        "salesforce/External_Career_Site/jobs"
    )
    assert all(method == "GET" for method, _ in calls[1:])
    assert "/wday/cxs/salesforce/External_Career_Site/job/" in calls[1][1]
    assert batch.source_url == "https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site"


def test_normalize_preserves_required_fields() -> None:
    fixture = load_fixture()
    posting = fixture["list"]["jobPostings"][0]
    raw_job = {**posting, "detail": fixture["details"][posting["externalPath"]]}
    connector, _ = make_connector(fixture)

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    info = raw_job["detail"]["jobPostingInfo"]
    assert job.platform == "workday"
    assert job.source_instance == "workday-salesforce"
    assert job.external_job_id == info["jobReqId"]
    assert job.title == info["title"]
    assert job.company == "100 Salesforce, Inc."
    assert job.description is not None
    assert "Job Category" in job.description
    assert job.location == info["location"]
    assert job.source_url == info["externalUrl"]
    assert job.application_url == info["externalUrl"]
    assert job.salary is None
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == info["startDate"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_falls_back_to_list_fields_without_detail() -> None:
    raw_job = dict(load_fixture()["list"]["jobPostings"][0])
    connector, _ = make_connector(load_fixture())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.company == "Salesforce"
    assert job.location == raw_job["locationsText"]
    assert job.employment_type is None
    assert job.source_url.startswith("https://salesforce.wd12.myworkdayjobs.com/en-US/")


def test_detail_failure_returns_partial_batch() -> None:
    fixture = load_fixture()
    external_path = fixture["list"]["jobPostings"][0]["externalPath"]
    connector, _ = make_connector(fixture, fail_detail_at=external_path)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(SOURCE)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 2


def test_max_jobs_returns_partial_batch() -> None:
    fixture = load_fixture()
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={**SOURCE.options, "max_jobs": 1},
    )
    connector, _ = make_connector(fixture)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["limit_reason"] == "max_jobs_reached"


def test_invalid_top_level_structure_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobPostings": "not-a-list"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = WorkdayConnector(HttpClient(client=client, max_retries=0))

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_posting_missing_required_field_is_rejected() -> None:
    raw_job = dict(load_fixture()["list"]["jobPostings"][0])
    raw_job.pop("externalPath")
    raw_job.pop("title")
    connector, _ = make_connector(load_fixture())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
