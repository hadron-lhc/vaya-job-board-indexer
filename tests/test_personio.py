from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.personio import PersonioConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "personio_lanch.xml"
SOURCE = SourceConfig(
    name="personio-lanch",
    platform="personio",
    tenant="lanch",
    company="Lanch",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_xml() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def make_connector(text: str, status_code: int = 200) -> PersonioConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=text, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PersonioConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_positions_and_metadata() -> None:
    connector = make_connector(load_xml())

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.request_urls == ["https://lanch.jobs.personio.de/xml?language=en"]
    assert batch.source_url == "https://lanch.jobs.personio.de/"


def test_normalize_preserves_required_fields() -> None:
    batch = make_connector(load_xml()).fetch(SOURCE)
    raw_job = batch.raw_jobs[1]
    connector = make_connector(load_xml())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "personio"
    assert job.source_instance == "personio-lanch"
    assert job.external_job_id == raw_job["id"]
    assert job.title == raw_job["name"]
    assert job.company == raw_job["subcompany"]
    assert job.description is not None
    assert "<h2>" in job.description
    assert job.location == raw_job["office"]
    assert job.source_url == f"https://lanch.jobs.personio.de/job/{raw_job['id']}?language=en"
    assert job.application_url is None
    assert job.salary is None
    assert job.employment_type == "Full-time"
    assert job.remote_status == "unknown"
    assert job.original_posted_at == raw_job["createdAt"]
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(make_connector(load_xml()).fetch(SOURCE).raw_jobs[1])
    for key in ("subcompany", "office", "schedule", "employmentType", "createdAt", "jobDescriptions"):
        raw_job.pop(key, None)
    connector = make_connector(load_xml())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.company == "Lanch"
    assert job.description is None
    assert job.location is None
    assert job.employment_type is None
    assert job.original_posted_at is None


def test_empty_feed_is_a_successful_empty_batch() -> None:
    connector = make_connector("<workzag-jobs></workzag-jobs>")

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert batch.raw_jobs == []
    assert batch.pagination["total"] == 0


def test_invalid_xml_is_rejected() -> None:
    connector = make_connector("not xml")

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_root_is_rejected() -> None:
    connector = make_connector("<rss></rss>")

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_position_missing_id_or_name_is_rejected() -> None:
    raw_job = dict(make_connector(load_xml()).fetch(SOURCE).raw_jobs[0])
    raw_job.pop("name")
    connector = make_connector(load_xml())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
