from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from job_indexer.connectors.rippling import RipplingConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "rippling_netatwork.json"
SOURCE = SourceConfig(
    name="rippling-netatwork",
    platform="rippling",
    tenant="netatwork",
    company="Net at Work",
    options={"page_size": 100},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_connector(
    fixture: dict,
    *,
    fail_detail_at: str | None = None,
    total_pages: int | None = None,
) -> tuple[RipplingConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        path = request.url.path
        if path.endswith("/jobs"):
            page = int(request.url.params.get("page", "0"))
            listing = fixture["list"]
            return httpx.Response(
                200,
                json={
                    "page": page,
                    "pageSize": listing["pageSize"],
                    "totalItems": listing["totalItems"],
                    "totalPages": total_pages if total_pages is not None else listing["totalPages"],
                    "items": listing["items"],
                },
                request=request,
            )
        job_id = path.rstrip("/").rsplit("/", 1)[-1]
        if fail_detail_at is not None and job_id == fail_detail_at:
            return httpx.Response(500, text="upstream error", request=request)
        return httpx.Response(200, json=fixture["details"][job_id], request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return RipplingConnector(HttpClient(client=client, max_retries=0)), calls


def first_detail(fixture: dict) -> dict[str, Any]:
    return next(iter(fixture["details"].values()))


def test_fetch_reads_list_and_details() -> None:
    fixture = load_fixture()
    connector, calls = make_connector(fixture)

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["pages"] == 1
    assert batch.pagination["total_items"] == 2
    assert batch.pagination["total_pages"] == 1
    assert len(calls) == 3
    assert "groupJobsByLocation=true" in calls[0]
    assert "pageSize=100" in calls[0]
    assert batch.source_url == "https://ats.rippling.com/netatwork/jobs"


def test_normalize_preserves_required_fields() -> None:
    fixture = load_fixture()
    raw_job = fixture["list"]["items"][0]
    raw_job = {**raw_job, "detail": fixture["details"][raw_job["id"]]}
    connector, _ = make_connector(fixture)

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "rippling"
    assert job.source_instance == "rippling-netatwork"
    assert job.external_job_id == raw_job["id"]
    assert job.title == raw_job["name"]
    assert job.company == "Net at Work, LLC"
    assert job.description is not None
    assert "About Net at Work" in job.description
    assert job.location == "Remote (United States)"
    assert job.source_url == raw_job["url"]
    assert job.application_url == raw_job["url"]
    assert job.salary is None
    assert job.employment_type == "Salaried, full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == "2026-05-12T14:30:06.593000-07:00"
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_falls_back_to_list_fields_without_detail() -> None:
    raw_job = dict(load_fixture()["list"]["items"][0])
    connector, _ = make_connector(load_fixture())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.company == "Net at Work"
    assert job.employment_type is None
    assert job.original_posted_at is None


def test_detail_failure_returns_partial_batch_with_list_jobs() -> None:
    fixture = load_fixture()
    first_id = str(fixture["list"]["items"][0]["id"])
    connector, _ = make_connector(fixture, fail_detail_at=first_id)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(SOURCE)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["returned"] == 2


def test_max_pages_returns_partial_batch() -> None:
    fixture = load_fixture()
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"page_size": 100, "max_pages": 1},
    )
    connector, _ = make_connector(fixture, total_pages=2)

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    assert exc_info.value.batch.complete is False
    assert exc_info.value.batch.pagination["limit_reason"] == "max_pages_reached"


def test_invalid_top_level_structure_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": "not-a-list"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = RipplingConnector(HttpClient(client=client, max_retries=0))

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_item_missing_required_field_is_rejected() -> None:
    raw_job = dict(load_fixture()["list"]["items"][0])
    raw_job.pop("url")
    connector, _ = make_connector(load_fixture())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
