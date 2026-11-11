from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from job_indexer.config import load_sources
from job_indexer.connectors.registry import build_connector
from job_indexer.errors import PartialFetchError
from job_indexer.http import HttpClient


pytestmark = pytest.mark.live

CONFIG = Path(__file__).resolve().parents[2] / "config" / "sources.json"
SOURCE_NAMES = [
    "greenhouse-stripe",
    "greenhouse-airbnb",
    "lever-palantir",
    "lever-spotify",
    "ashby-ashby",
    "ashby-openai",
    "workable-huggingface",
    "workable-runware",
    "smartrecruiters-canva",
    "smartrecruiters-innergy",
    "recruitee-bunq",
    "recruitee-tellent",
    "pinpoint-avaaz",
    "pinpoint-workwithus",
    "personio-lanch",
    "personio-deskbird",
    "teamtailor-bankgirotab",
    "teamtailor-doconomy",
    "rippling-netatwork",
    "rippling-realwork",
    "workday-salesforce",
    "workday-adobe",
    "breezy-breezyhr",
    "breezy-prep-academy",
    "bamboohr-flyio",
    "bamboohr-acme",
    "jazzhr-snapsheet",
    "jazzhr-loccitane",
    "niceboard-afa",
    "niceboard-linkinbio",
]


@pytest.mark.parametrize("source_name", SOURCE_NAMES)
def test_live_source_returns_normalizable_jobs(source_name: str) -> None:
    sources = load_sources(CONFIG)
    source = sources[source_name]

    with HttpClient() as http:
        connector = build_connector(source.platform, http)
        try:
            batch = connector.fetch(source)
            assert batch.complete is True
        except PartialFetchError as exc:
            if "max_jobs" not in source.options:
                raise
            batch = exc.batch
            assert batch.complete is False
            assert batch.pagination["limit_reason"] == "max_jobs_reached"
    assert len(batch.raw_jobs) > 0

    job = connector.normalize(batch.raw_jobs[0], source, datetime.now(timezone.utc))
    assert job.external_job_id
    assert job.title
    assert job.company
    assert job.source_url.startswith("https://")
    if source.platform in {
        "lever",
        "ashby",
        "workable",
        "smartrecruiters",
        "recruitee",
        "pinpoint",
        "teamtailor",
        "rippling",
        "workday",
        "breezy",
        "bamboohr",
        "jazzhr",
        "niceboard",
    }:
        assert job.application_url is not None
