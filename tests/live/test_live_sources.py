from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from job_indexer.config import load_sources
from job_indexer.connectors.registry import build_connector
from job_indexer.http import HttpClient


pytestmark = pytest.mark.live

CONFIG = Path(__file__).resolve().parents[2] / "config" / "sources.json"
SOURCE_NAMES = [
    "greenhouse-stripe",
    "greenhouse-airbnb",
    "lever-palantir",
    "lever-spotify",
]


@pytest.mark.parametrize("source_name", SOURCE_NAMES)
def test_live_source_returns_normalizable_jobs(source_name: str) -> None:
    sources = load_sources(CONFIG)
    source = sources[source_name]

    with HttpClient() as http:
        connector = build_connector(source.platform, http)
        batch = connector.fetch(source)

    assert batch.complete is True
    assert len(batch.raw_jobs) > 0

    job = connector.normalize(batch.raw_jobs[0], source, datetime.now(timezone.utc))
    assert job.external_job_id
    assert job.title
    assert job.company
    assert job.source_url.startswith("https://")
    if source.platform == "lever":
        assert job.application_url is not None
