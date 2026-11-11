from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.jazzhr import JazzHRConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = SourceConfig(
    name="jazzhr-acme",
    platform="jazzhr",
    tenant="acme",
    company="Acme",
    options={"max_jobs": 10},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_list() -> str:
    return (FIXTURES / "jazzhr_list.html").read_text(encoding="utf-8")


def load_detail() -> str:
    return (FIXTURES / "jazzhr_detail.html").read_text(encoding="utf-8")


def make_connector(listing: str, detail: str | None = None) -> tuple[JazzHRConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/apply/jobs":
            return httpx.Response(200, text=listing, request=request)
        return httpx.Response(200, text=detail or load_detail(), request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return JazzHRConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_reads_list_and_details() -> None:
    connector, calls = make_connector(load_list())

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert calls[0] == "https://acme.applytojob.com/apply/jobs"
    assert calls[1] == "https://acme.applytojob.com/apply/jobs/details/7dY1TUAJrl"
    assert batch.source_url == "https://acme.applytojob.com/apply"


def test_normalize_preserves_required_fields() -> None:
    connector, _ = make_connector(load_list())
    raw_job = connector.fetch(SOURCE).raw_jobs[0]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "jazzhr"
    assert job.external_job_id == "7dY1TUAJrl"
    assert job.title == "Account Manager"
    assert job.company == "Snapsheet"
    assert job.description == "<p>Own customer relationships.</p>"
    assert job.location == "Chicago, IL, US"
    assert job.source_url == "https://acme.applytojob.com/apply/jobs/details/7dY1TUAJrl"
    assert job.application_url == job.source_url
    assert job.salary == "95000-120000 USD YEAR"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == "2026-09-15"


def test_normalize_falls_back_to_list_title() -> None:
    connector, _ = make_connector(load_list())
    raw_job = dict(connector.fetch(SOURCE).raw_jobs[1])
    raw_job.pop("_jsonld")

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.title == "Software Engineer"
    assert job.description is None
    assert job.location is None
    assert job.remote_status == "unknown"
    assert job.original_posted_at is None


def test_max_jobs_returns_partial_batch() -> None:
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"max_jobs": 1},
    )
    connector, _ = make_connector(load_list())

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["limit_reason"] == "max_jobs_reached"


def test_empty_list_is_a_successful_empty_batch() -> None:
    connector, _ = make_connector("<html><body>No jobs</body></html>")

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0


def test_invalid_job_missing_required_fields_is_rejected() -> None:
    raw_job = {"id": "abc", "title": "Role"}
    connector, _ = make_connector(load_list())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
