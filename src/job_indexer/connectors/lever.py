from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    epoch_ms_to_iso,
    format_salary,
    non_empty_str,
    normalize_remote_status,
    to_utc_iso,
)


class LeverConnector:
    platform = "lever"
    _ALLOWED_HOSTS = frozenset({"api.lever.co", "api.eu.lever.co"})

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _api_host(self, source: SourceConfig) -> str:
        host = source.options.get("api_host", "api.lever.co")
        if host not in self._ALLOWED_HOSTS:
            raise ValueError(f"unsupported Lever API host: {host!r}")
        return str(host)

    def _page_size(self, source: SourceConfig) -> int:
        raw = source.options.get("page_size", 100)
        try:
            page_size = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Lever page_size: {raw!r}") from exc
        if page_size < 1 or page_size > 100:
            raise ValueError("Lever page_size must be between 1 and 100")
        return page_size

    @staticmethod
    def _partial_batch(
        *,
        site: str,
        page_size: int,
        jobs: list[dict[str, Any]],
        request_urls: list[str],
        pages: int,
        payloads: list[Any],
        limit_reason: str | None = None,
    ) -> FetchBatch:
        pagination: dict[str, Any] = {
            "page_size": page_size,
            "pages": pages,
            "returned": len(jobs),
            "complete": False,
        }
        if limit_reason is not None:
            pagination["limit_reason"] = limit_reason
        return FetchBatch(
            raw_jobs=jobs,
            request_urls=request_urls,
            source_url=f"https://jobs.lever.co/{site}",
            pagination=pagination,
            complete=False,
            raw_payloads=payloads,
        )

    def fetch(self, source: SourceConfig) -> FetchBatch:
        host = self._api_host(source)
        site = quote(source.tenant, safe="")
        base_url = f"https://{host}/v0/postings/{site}"
        page_size = self._page_size(source)

        jobs: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_urls: list[str] = []
        skip = 0
        pages = 0

        while True:
            try:
                response = self.http.get(
                    base_url,
                    params={"mode": "json", "limit": page_size, "skip": skip},
                )
            except HttpError as exc:
                if jobs:
                    raise PartialFetchError(
                        str(exc),
                        self._partial_batch(
                            site=site,
                            page_size=page_size,
                            jobs=jobs,
                            request_urls=request_urls,
                            pages=pages,
                            payloads=payloads,
                        ),
                    ) from exc
                raise

            try:
                data = response.json()
            except ValueError as exc:
                if jobs:
                    raise PartialFetchError(
                        f"Lever response is not valid JSON after {pages} page(s): {exc}",
                        self._partial_batch(
                            site=site,
                            page_size=page_size,
                            jobs=jobs,
                            request_urls=request_urls,
                            pages=pages,
                            payloads=payloads,
                        ),
                    ) from exc
                raise InvalidResponseError("Lever response is not valid JSON") from exc
            if not isinstance(data, list):
                if jobs:
                    raise PartialFetchError(
                        "Lever response must be a JSON array",
                        self._partial_batch(
                            site=site,
                            page_size=page_size,
                            jobs=jobs,
                            request_urls=request_urls,
                            pages=pages,
                            payloads=payloads,
                        ),
                    )
                raise InvalidResponseError("Lever response must be a JSON array")

            jobs.extend(data)
            payloads.append(data)
            request_urls.append(str(response.url))
            pages += 1

            if len(data) < page_size:
                break

            skip += len(data)
            if pages >= 100:
                raise PartialFetchError(
                    "Lever pagination exceeded 100 pages",
                    self._partial_batch(
                        site=site,
                        page_size=page_size,
                        jobs=jobs,
                        request_urls=request_urls,
                        pages=pages,
                        payloads=payloads,
                        limit_reason="max_pages_reached",
                    ),
                )

        return FetchBatch(
            raw_jobs=jobs,
            request_urls=request_urls,
            source_url=f"https://jobs.lever.co/{site}",
            pagination={
                "page_size": page_size,
                "pages": pages,
                "returned": len(jobs),
                "complete": True,
            },
            complete=True,
            raw_payloads=payloads,
        )

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Lever job must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("text"))
        source_url = non_empty_str(raw_job.get("hostedUrl"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Lever job is missing id, text, or hostedUrl")

        categories = raw_job.get("categories")
        if not isinstance(categories, dict):
            categories = {}

        location = non_empty_str(categories.get("location")) or non_empty_str(raw_job.get("country"))
        description = non_empty_str(raw_job.get("description")) or non_empty_str(
            raw_job.get("descriptionPlain")
        )
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=source.company,
            description=description,
            location=location,
            source_url=source_url,
            application_url=non_empty_str(raw_job.get("applyUrl")),
            salary=format_salary(raw_job.get("salaryRange")),
            employment_type=non_empty_str(categories.get("commitment")),
            remote_status=normalize_remote_status(raw_job.get("workplaceType"), location),
            original_posted_at=epoch_ms_to_iso(raw_job.get("createdAt")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )
