from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx

from .errors import HttpError


DEFAULT_USER_AGENT = "vaya-job-board-indexer/0.1"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class HttpClient:
    """Small synchronous HTTP client with bounded retries and clear errors."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_base: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        client: httpx.Client | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self.user_agent = user_agent
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        attempt = 0
        while True:
            try:
                response = self._client.get(url, params=params, headers=request_headers)
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise HttpError(
                        f"request failed after {attempt + 1} attempt(s): {exc}",
                        url=url,
                    ) from exc
                self._sleep(self._backoff_delay(attempt))
                attempt += 1
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else self._backoff_delay(attempt)
                self._sleep(min(max(delay, 0.0), 60.0))
                attempt += 1
                continue

            if response.status_code >= 400:
                body_preview = response.text[:300]
                raise HttpError(
                    f"HTTP {response.status_code} for {response.url}",
                    url=str(response.url),
                    status_code=response.status_code,
                    body_preview=body_preview,
                )

            return response

    def _backoff_delay(self, attempt: int) -> float:
        base = min(self.backoff_base * (2**attempt), 8.0)
        return base + random.uniform(0.0, 0.25)

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        value = value.strip()
        try:
            return float(value)
        except ValueError:
            pass

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return (retry_at - datetime.now(timezone.utc)).total_seconds()
