from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from ..models import FetchBatch, JobListing, SourceConfig


class Connector(Protocol):
    platform: str

    def fetch(self, source: SourceConfig) -> FetchBatch:
        ...

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        ...
