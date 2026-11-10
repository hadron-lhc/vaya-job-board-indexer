from __future__ import annotations

from typing import Any


class JobIndexerError(Exception):
    """Base class for expected indexer errors."""


class HttpError(JobIndexerError):
    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status_code: int | None = None,
        body_preview: str | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.body_preview = body_preview


class InvalidResponseError(JobIndexerError):
    """The remote response did not match the documented shape."""


class PartialFetchError(JobIndexerError):
    """Some pages were fetched, but a later request failed."""

    def __init__(self, message: str, batch: Any) -> None:
        super().__init__(message)
        self.batch = batch
