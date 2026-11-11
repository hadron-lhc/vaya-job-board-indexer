from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_indexer.connectors.breezy import BreezyConnector
from job_indexer.errors import InvalidResponseError, PartialFetchError
from job_indexer.http import HttpClient
from job_indexer.models import SourceConfig


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = SourceConfig(
    name="breezy-acme",
    platform="breezy",
    tenant="acme",
    company="Acme",
    options={"max_jobs": 10},
)
CHECKED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def load_board() -> list:
    return json.loads((FIXTURES / "breezy_board.json").read_text(encoding="utf-8"))


def make_connector(board: list, detail: str | None = None) -> tuple[BreezyConnector, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/json":
            return httpx.Response(200, json=board, request=request)
        return httpx.Response(200, text=detail or "", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BreezyConnector(HttpClient(client=client, max_retries=0)), calls


def test_fetch_reads_board_and_detail() -> None:
    connector, calls = make_connector(
        load_board(),
        (FIXTURES / "breezy_detail.html").read_text(encoding="utf-8"),
    )

    batch = connector.fetch(SOURCE)

    assert batch.complete is True
    assert len(batch.raw_jobs) == 2
    assert batch.pagination["total"] == 2
    assert calls[0] == "https://acme.breezy.hr/json"
    assert batch.source_url == "https://acme.breezy.hr/"


def test_normalize_preserves_required_fields() -> None:
    connector, _ = make_connector(
        load_board(),
        (FIXTURES / "breezy_detail.html").read_text(encoding="utf-8"),
    )
    raw_job = connector.fetch(SOURCE).raw_jobs[0]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.platform == "breezy"
    assert job.external_job_id == "abc123-data-engineer"
    assert job.title == "Data Engineer"
    assert job.company == "Acme"
    assert job.description == "<p>Build reliable data pipelines.</p>"
    assert job.location == "Remote"
    assert job.source_url == raw_job["url"]
    assert job.application_url == raw_job["url"]
    assert job.salary == "120000-160000 USD YEAR"
    assert job.employment_type == "Full-time"
    assert job.remote_status == "remote"
    assert job.original_posted_at == "2026-11-01T10:00:00.000Z"


def test_normalize_falls_back_to_board_fields() -> None:
    connector, _ = make_connector(load_board())
    raw_job = connector.fetch(SOURCE).raw_jobs[1]

    job = connector.normalize(raw_job, SOURCE, CHECKED_AT)

    assert job.description is None
    assert job.location == "Austin, TX"
    assert job.salary == "$25 / hour"
    assert job.employment_type == "Part-time"
    assert job.remote_status == "unknown"


def test_max_jobs_returns_partial_batch() -> None:
    source = SourceConfig(
        name=SOURCE.name,
        platform=SOURCE.platform,
        tenant=SOURCE.tenant,
        company=SOURCE.company,
        options={"max_jobs": 1},
    )
    connector, _ = make_connector(load_board())

    with pytest.raises(PartialFetchError) as exc_info:
        connector.fetch(source)

    batch = exc_info.value.batch
    assert batch.complete is False
    assert len(batch.raw_jobs) == 1
    assert batch.pagination["limit_reason"] == "max_jobs_reached"


def test_invalid_board_shape_is_rejected() -> None:
    connector, _ = make_connector({"jobs": []})

    with pytest.raises(InvalidResponseError):
        connector.fetch(SOURCE)


def test_invalid_job_missing_required_fields_is_rejected() -> None:
    raw_job = dict(load_board()[0])
    raw_job.pop("url")
    connector, _ = make_connector(load_board())

    with pytest.raises(InvalidResponseError):
        connector.normalize(raw_job, SOURCE, CHECKED_AT)
