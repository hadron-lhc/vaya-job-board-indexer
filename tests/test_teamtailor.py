from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.teamtailor import TeamtailorConnector
from job_indexer.errors import InvalidResponseError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "teamtailor_bankgirotab.xml"
SOURCE = SourceConfig(
    name="teamtailor-bankgirotab",
    platform="teamtailor",
    tenant="bankgirotab",
    company="Bankgirot",
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_xml() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def make_connector(text: str) -> TeamtailorConnector:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=text, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TeamtailorConnector(HttpClient(client=client, max_retries=0))


def test_fetch_reads_items_and_metadata() -> None:
    connector = make_connector(load_xml())

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert batch.request_urls == ["https://bankgirotab.teamtailor.com/jobs.rss"]
    assert batch.source_url == "https://bankgirotab.teamtailor.com/jobs"


def test_normalize_preserves_required_fields() -> None:
    batch = make_connector(load_xml()).fetch(SOURCE)
    raw_job = batch.raw_jobs[0]
    connector = make_connector(load_xml())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "teamtailor"
    assert job.source_instance == "teamtailor-bankgirotab"
    assert job.external_job_id == raw_job["guid"]
    assert job.title == raw_job["title"]
    assert job.company == "Bankgirot"
    assert job.description is not None
    assert job.location == "Stockholm, Sweden"
    assert job.source_url == raw_job["link"]
    assert job.application_url == raw_job["link"]
    assert job.salary is None
    assert job.employment_type is None
    assert job.remote_status == "onsite"
    assert job.original_posted_at == "2026-10-22T11:01:31+00:00"
    assert job.first_seen_at == "2026-11-10T12:00:00+00:00"


def test_normalize_handles_missing_optional_fields() -> None:
    raw_job = dict(make_connector(load_xml()).fetch(SOURCE).raw_jobs[0])
    for key in ("description", "guid", "locations", "pubDate", "remoteStatus"):
        raw_job.pop(key, None)
    connector = make_connector(load_xml())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.external_job_id == raw_job["link"]
    assert job.location is None
    assert job.original_posted_at is None
    assert job.remote_status == "unknown"


def test_normalize_remote_without_location_uses_remote_label() -> None:
    raw_job = dict(make_connector(load_xml()).fetch(SOURCE).raw_jobs[0])
    raw_job["locations"] = []
    raw_job["remoteStatus"] = "fully"
    connector = make_connector(load_xml())

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.location == "Remote"
    assert job.remote_status == "remote"


def test_invalid_xml_is_rejected() -> None:
    connector = make_connector("not xml")

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_root_is_rejected() -> None:
    connector = make_connector("<feed></feed>")

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_item_missing_title_or_link_is_rejected() -> None:
    raw_job = dict(make_connector(load_xml()).fetch(SOURCE).raw_jobs[0])
    raw_job.pop("link")
    connector = make_connector(load_xml())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
