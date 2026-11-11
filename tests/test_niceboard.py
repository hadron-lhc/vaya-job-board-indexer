from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.niceboard import NiceboardConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = SourceConfig(
    name="niceboard-acme",
    platform="niceboard",
    tenant="acme",
    company="Acme",
    options={"max_jobs": 10, "page_size": 1},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_page(number: int) -> dict:
    return json.loads(
        (FIXTURES / f"niceboard_page{number}.json").read_text(encoding="utf-8")
    )


def make_connector(pages: dict[int, dict]) -> tuple[NiceboardConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=pages.get(page, {"jobs": [], "count": 0}), request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return NiceboardConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_paginates_until_total() -> None:
    connector, calls = make_connector({1: load_page(1), 2: load_page(2)})

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert len(calls) == 2
    assert "page=1" in calls[0]
    assert "page=2" in calls[1]
    assert batch.source_url == "https://acme.niceboard.co/"


def test_normalize_preserves_required_fields() -> None:
    connector, _ = make_connector({1: load_page(1), 2: load_page(2)})
    raw_job = connector.fetch(SOURCE).raw_jobs[0]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "niceboard"
    assert job.external_job_id == "2583310"
    assert job.title == "Assistant Director"
    assert job.company == "Susquehanna University"
    assert job.description == "<p>Lead student programs.</p>"
    assert job.location == "Selinsgrove, Pennsylvania, United States"
    assert job.source_url == (
        "https://acme.niceboard.co/job/2583310-assistant-director-susquehanna-university"
    )
    assert job.application_url == "https://example.com/apply/2583310"
    assert job.salary == "60000-70000 USD year"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "unknown"
    assert job.original_posted_at == "2026-10-27T18:53:12.188Z"


def test_normalize_remote_and_email_application() -> None:
    connector, _ = make_connector({1: load_page(1), 2: load_page(2)})
    raw_job = connector.fetch(SOURCE).raw_jobs[1]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.location == "Remote"
    assert job.application_url == "mailto:jobs@example.com"
    assert job.remote_status == "remote"
    assert job.salary is None
    assert job.employment_type == "Contract"


def test_max_jobs_returns_partial_batch() -> None:
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"max_jobs": 1, "page_size": 1},
    )
    connector, _ = make_connector({1: load_page(1), 2: load_page(2)})

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["limit_reason"] == "max_jobs_reached"


def test_invalid_shape_is_rejected() -> None:
    connector, _ = make_connector({1: {"jobs": "not-a-list", "count": 1}})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_job_missing_required_fields_is_rejected() -> None:
    raw_job = dict(load_page(1)["jobs"][0])
    raw_job.pop("title")
    connector, _ = make_connector({1: load_page(1)})

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
