from __future__ import annotations

import json
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


class NiceboardConnector:
    platform = "niceboard"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _api_url(self, source: SourceConfig) -> str:
        return f"https://{quote(source.tenant, safe='')}.niceboard.co/api/jobs"

    def _max_jobs(self, source: SourceConfig) -> int:
        raw = source.options.get("max_jobs", 100)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Niceboard max_jobs: {raw!r}") from exc
        if value < 1:
            raise ValueError("Niceboard max_jobs must be at least 1")
        return value

    def _page_size(self, source: SourceConfig) -> int:
        raw = source.options.get("page_size", 100)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Niceboard page_size: {raw!r}") from exc
        if value < 1 or value > 100:
            raise ValueError("Niceboard page_size must be between 1 and 100")
        return value

    def _params(self, *, page: int, limit: int) -> dict[str, str]:
        return {
            "company": "all",
            "jobtype": json.dumps([]),
            "category": json.dumps([]),
            "secondary_category": json.dumps([]),
            "tags": json.dumps([]),
            "city": json.dumps([]),
            "state": json.dumps([]),
            "country": json.dumps([]),
            "custom_fields": json.dumps({}),
            "remote_ok": "false",
            "remote_only": "false",
            "salary_timeframe": "",
            "salary_min": "",
            "salary_max": "",
            "keyword": "",
            "limit": str(limit),
            "page": str(page),
            "sortby": "newest",
        }

    def fetch(self, source: SourceConfig) -> FetchBatch:
        max_jobs = self._max_jobs(source)
        page_size = self._page_size(source)
        raw_jobs: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_urls: list[str] = []
        page = 1
        total: int | None = None
        max_pages = 50

        while len(raw_jobs) < max_jobs:
            limit = min(page_size, max_jobs - len(raw_jobs))
            try:
                response = self.http.get(
                    self._api_url(source),
                    params=self._params(page=page, limit=limit),
                )
            except HttpError as exc:
                if raw_jobs:
                    raise PartialFetchError(
                        str(exc),
                        self._batch(
                            source=source,
                            raw_jobs=raw_jobs,
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total if total is not None else len(raw_jobs),
                            complete=False,
                            limit_reason="http_error",
                        ),
                    ) from exc
                raise

            try:
                data = response.json()
            except ValueError as exc:
                if raw_jobs:
                    raise PartialFetchError(
                        f"Niceboard response is not valid JSON after {page} page(s)",
                        self._batch(
                            source=source,
                            raw_jobs=raw_jobs,
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total if total is not None else len(raw_jobs),
                            complete=False,
                            limit_reason="invalid_json",
                        ),
                    ) from exc
                raise InvalidResponseError("Niceboard response is not valid JSON") from exc

            if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
                if raw_jobs:
                    raise PartialFetchError(
                        "Niceboard response must contain a jobs array",
                        self._batch(
                            source=source,
                            raw_jobs=raw_jobs,
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total if total is not None else len(raw_jobs),
                            complete=False,
                            limit_reason="invalid_shape",
                        ),
                    )
                raise InvalidResponseError("Niceboard response must contain a jobs array")

            jobs = data["jobs"]
            if any(not isinstance(item, dict) for item in jobs):
                raise InvalidResponseError("Niceboard jobs must be objects")
            count = data.get("count")
            if isinstance(count, int) and not isinstance(count, bool):
                total = count

            raw_jobs.extend(jobs)
            payloads.append(data)
            request_urls.append(str(response.url))

            if not jobs:
                break
            if total is not None and len(raw_jobs) >= total:
                break
            if len(jobs) < limit:
                break
            page += 1
            if page > max_pages:
                raise PartialFetchError(
                    "Niceboard pagination exceeded 50 pages",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        total=total if total is not None else len(raw_jobs),
                        complete=False,
                        limit_reason="max_pages_reached",
                    ),
                )

        if total is not None and len(raw_jobs) < total:
            raise PartialFetchError(
                "Niceboard result capped by max_jobs",
                self._batch(
                    source=source,
                    raw_jobs=raw_jobs,
                    request_urls=request_urls,
                    payloads=payloads,
                    total=total,
                    complete=False,
                    limit_reason="max_jobs_reached",
                ),
            )

        return self._batch(
            source=source,
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            payloads=payloads,
            total=total if total is not None else len(raw_jobs),
            complete=True,
        )

    def _batch(
        self,
        *,
        source: SourceConfig,
        raw_jobs: list[dict[str, Any]],
        request_urls: list[str],
        payloads: list[Any],
        total: int,
        complete: bool,
        limit_reason: str | None = None,
    ) -> FetchBatch:
        pagination: dict[str, Any] = {
            "total": total,
            "returned": len(raw_jobs),
            "complete": complete,
        }
        if limit_reason is not None:
            pagination["limit_reason"] = limit_reason
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://{quote(source.tenant, safe='')}.niceboard.co/",
            pagination=pagination,
            complete=complete,
            raw_payloads=payloads,
        )

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Niceboard job must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("title"))
        if external_id is None or title is None:
            raise InvalidResponseError("Niceboard job is missing id or title")

        source_url = self._source_url(source, raw_job, str(external_id))
        location = self._location(raw_job)
        remote = raw_job.get("is_remote") is True or raw_job.get("remote_only") is True
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=non_empty_str(raw_job.get("company_name")) or source.company,
            description=non_empty_str(raw_job.get("description_html")),
            location=location,
            source_url=source_url,
            application_url=self._application_url(raw_job, source_url),
            salary=format_salary(
                {
                    "min": raw_job.get("salary_min"),
                    "max": raw_job.get("salary_max"),
                    "currency": raw_job.get("salary_currency"),
                    "interval": raw_job.get("salary_timeframe"),
                }
            ),
            employment_type=normalize_employment_type(self._job_type(raw_job)),
            remote_status=normalize_remote_status(
                "remote" if remote else None,
                location,
            ),
            original_posted_at=non_empty_str(raw_job.get("published_at")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _source_url(
        source: SourceConfig,
        raw_job: dict[str, Any],
        external_id: str,
    ) -> str:
        slug = non_empty_str(raw_job.get("slug")) or "job"
        path = f"/job/{external_id}-{slug}"
        if raw_job.get("anonymity_enabled") is not True:
            company_slug = non_empty_str(raw_job.get("company_slug"))
            if company_slug:
                path = f"{path}-{company_slug}"
        return f"https://{quote(source.tenant, safe='')}.niceboard.co{path}"

    @staticmethod
    def _application_url(raw_job: dict[str, Any], source_url: str) -> str:
        apply_url = non_empty_str(raw_job.get("apply_url"))
        if apply_url is not None:
            return apply_url
        apply_email = non_empty_str(raw_job.get("apply_email"))
        if apply_email is not None:
            return f"mailto:{apply_email}"
        return source_url

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        location = raw_job.get("location")
        if isinstance(location, dict):
            parts = [
                non_empty_str(location.get("city_long") or location.get("city")),
                non_empty_str(location.get("state_long") or location.get("state")),
                non_empty_str(location.get("country_long") or location.get("country")),
            ]
            text = ", ".join(part for part in parts if part)
            if text:
                return text
        location_name = non_empty_str(raw_job.get("location_name"))
        if location_name is not None:
            return location_name
        if raw_job.get("is_remote") is True or raw_job.get("remote_only") is True:
            return "Remote"
        return None

    @staticmethod
    def _job_type(raw_job: dict[str, Any]) -> str | None:
        value = raw_job.get("jobtype")
        if isinstance(value, dict):
            return non_empty_str(value.get("name")) or non_empty_str(value.get("slug"))
        return non_empty_str(value)
