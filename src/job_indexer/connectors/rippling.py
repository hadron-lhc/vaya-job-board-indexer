from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    format_salary,
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    to_utc_iso,
)


class RipplingConnector:
    platform = "rippling"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _list_url(self, source: SourceConfig) -> str:
        slug = quote(source.tenant, safe="")
        return f"https://ats.rippling.com/api/v2/board/{slug}/jobs"

    def _detail_url(self, source: SourceConfig, external_id: str) -> str:
        slug = quote(source.tenant, safe="")
        job_id = quote(external_id, safe="")
        return f"https://ats.rippling.com/api/v2/board/{slug}/jobs/{job_id}"

    def _page_size(self, source: SourceConfig) -> int:
        raw = source.options.get("page_size", 100)
        try:
            page_size = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Rippling page_size: {raw!r}") from exc
        if page_size < 1 or page_size > 1000:
            raise ValueError("Rippling page_size must be between 1 and 1000")
        return page_size

    def _max_pages(self, source: SourceConfig) -> int:
        raw = source.options.get("max_pages", 50)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Rippling max_pages: {raw!r}") from exc
        if value < 1:
            raise ValueError("Rippling max_pages must be >= 1")
        return value

    def _batch(
        self,
        *,
        source: SourceConfig,
        raw_jobs: list[dict[str, Any]],
        request_urls: list[str],
        payloads: list[Any],
        pages: int,
        total_pages: int | None,
        total_items: int | None,
        complete: bool,
        limit_reason: str | None = None,
    ) -> FetchBatch:
        pagination: dict[str, Any] = {
            "pages": pages,
            "returned": len(raw_jobs),
            "total_items": total_items,
            "total_pages": total_pages,
            "complete": complete,
        }
        if limit_reason is not None:
            pagination["limit_reason"] = limit_reason
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://ats.rippling.com/{quote(source.tenant, safe='')}/jobs",
            pagination=pagination,
            complete=complete,
            raw_payloads=payloads,
        )

    def fetch(self, source: SourceConfig) -> FetchBatch:
        list_url = self._list_url(source)
        page_size = self._page_size(source)
        max_pages = self._max_pages(source)

        items: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_urls: list[str] = []
        page = 0
        total_pages: int | None = None
        total_items: int | None = None

        while True:
            try:
                response = self.http.get(
                    list_url,
                    params={
                        "page": page,
                        "pageSize": page_size,
                        "groupJobsByLocation": "true",
                    },
                )
            except HttpError as exc:
                if items:
                    raise PartialFetchError(
                        str(exc),
                        self._batch(
                            source=source,
                            raw_jobs=[dict(item) for item in items],
                            request_urls=request_urls,
                            payloads=payloads,
                            pages=page,
                            total_pages=total_pages,
                            total_items=total_items,
                            complete=False,
                        ),
                    ) from exc
                raise

            try:
                data = response.json()
            except ValueError as exc:
                if items:
                    raise PartialFetchError(
                        f"Rippling response is not valid JSON after {page} page(s): {exc}",
                        self._batch(
                            source=source,
                            raw_jobs=[dict(item) for item in items],
                            request_urls=request_urls,
                            payloads=payloads,
                            pages=page,
                            total_pages=total_pages,
                            total_items=total_items,
                            complete=False,
                        ),
                    ) from exc
                raise InvalidResponseError("Rippling response is not valid JSON") from exc

            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                if items:
                    raise PartialFetchError(
                        "Rippling response must contain an items array",
                        self._batch(
                            source=source,
                            raw_jobs=[dict(item) for item in items],
                            request_urls=request_urls,
                            payloads=payloads,
                            pages=page,
                            total_pages=total_pages,
                            total_items=total_items,
                            complete=False,
                        ),
                    )
                raise InvalidResponseError("Rippling response must contain an items array")

            page_items = data["items"]
            if any(not isinstance(item, dict) for item in page_items):
                raise InvalidResponseError("Rippling items must be objects")
            items.extend(page_items)
            payloads.append(data)
            request_urls.append(str(response.url))
            page += 1

            total_pages_value = data.get("totalPages")
            if isinstance(total_pages_value, int) and not isinstance(total_pages_value, bool):
                total_pages = total_pages_value
            total_items_value = data.get("totalItems")
            if isinstance(total_items_value, int) and not isinstance(total_items_value, bool):
                total_items = total_items_value

            if not page_items:
                break
            if total_pages is not None and page >= total_pages:
                break
            if page >= max_pages:
                raise PartialFetchError(
                    "Rippling pagination exceeded max_pages",
                    self._batch(
                        source=source,
                        raw_jobs=[dict(item) for item in items],
                        request_urls=request_urls,
                        payloads=payloads,
                        pages=page,
                        total_pages=total_pages,
                        total_items=total_items,
                        complete=False,
                        limit_reason="max_pages_reached",
                    ),
                )

        raw_jobs = [dict(item) for item in items]
        for index, item in enumerate(raw_jobs):
            external_id = item.get("id")
            if external_id is None:
                raise InvalidResponseError("Rippling item is missing id")
            try:
                response = self.http.get(self._detail_url(source, str(external_id)))
            except HttpError as exc:
                raise PartialFetchError(
                    str(exc),
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        pages=page,
                        total_pages=total_pages,
                        total_items=total_items,
                        complete=False,
                    ),
                ) from exc
            try:
                detail = response.json()
            except ValueError as exc:
                raise PartialFetchError(
                    f"Rippling detail response is not valid JSON: {exc}",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        pages=page,
                        total_pages=total_pages,
                        total_items=total_items,
                        complete=False,
                    ),
                ) from exc
            if not isinstance(detail, dict):
                raise PartialFetchError(
                    "Rippling detail response must be an object",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        pages=page,
                        total_pages=total_pages,
                        total_items=total_items,
                        complete=False,
                    ),
                )
            raw_jobs[index] = {**item, "detail": detail}
            payloads.append(detail)
            request_urls.append(str(response.url))

        return self._batch(
            source=source,
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            payloads=payloads,
            pages=page,
            total_pages=total_pages,
            total_items=total_items,
            complete=True,
        )

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Rippling item must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("name"))
        source_url = non_empty_str(raw_job.get("url"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Rippling item is missing id, name, or url")

        detail = raw_job.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        location = self._location(raw_job, detail)
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=non_empty_str(detail.get("companyName")) or source.company,
            description=self._description(detail),
            location=location,
            source_url=source_url,
            application_url=source_url,
            salary=self._salary(detail),
            employment_type=self._employment_type(detail),
            remote_status=self._remote_status(raw_job, location),
            original_posted_at=non_empty_str(detail.get("createdOn")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _location(raw_job: dict[str, Any], detail: dict[str, Any]) -> str | None:
        labels: list[str] = []
        locations = raw_job.get("locations")
        if isinstance(locations, list):
            for location in locations:
                if not isinstance(location, dict):
                    continue
                label = non_empty_str(location.get("name"))
                if label and label not in labels:
                    labels.append(label)
        if labels:
            return "; ".join(labels)
        work_locations = detail.get("workLocations")
        if isinstance(work_locations, list):
            for value in work_locations:
                label = non_empty_str(value)
                if label and label not in labels:
                    labels.append(label)
        return "; ".join(labels) or None

    @staticmethod
    def _description(detail: dict[str, Any]) -> str | None:
        description = detail.get("description")
        if not isinstance(description, dict):
            return None
        parts = [
            non_empty_str(description.get("company")),
            non_empty_str(description.get("role")),
        ]
        return "\n".join(part for part in parts if part) or None

    @staticmethod
    def _salary(detail: dict[str, Any]) -> str | None:
        ranges = detail.get("payRangeDetails")
        if not isinstance(ranges, list) or not ranges:
            return None
        first = ranges[0]
        if not isinstance(first, dict):
            return None
        return format_salary(
            {
                "min": first.get("rangeStart"),
                "max": first.get("rangeEnd"),
                "currency": first.get("currency"),
                "interval": first.get("frequency"),
            }
        )

    @staticmethod
    def _employment_type(detail: dict[str, Any]) -> str | None:
        value = detail.get("employmentType")
        if isinstance(value, dict):
            return normalize_employment_type(value.get("id") or value.get("label"))
        return normalize_employment_type(value)

    @staticmethod
    def _remote_status(raw_job: dict[str, Any], location: str | None) -> str:
        workplace_types: set[str] = set()
        locations = raw_job.get("locations")
        if isinstance(locations, list):
            for item in locations:
                if isinstance(item, dict):
                    value = non_empty_str(item.get("workplaceType"))
                    if value:
                        workplace_types.add(value.upper())
        if "REMOTE" in workplace_types:
            return "remote"
        if "HYBRID" in workplace_types:
            return "hybrid"
        if workplace_types and workplace_types <= {"ON_SITE", "ONSITE"}:
            return "onsite"
        return normalize_remote_status(None, location)
