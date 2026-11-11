from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    to_utc_iso,
)


class BambooHRConnector:
    platform = "bamboohr"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _list_url(self, source: SourceConfig) -> str:
        return f"https://{quote(source.tenant, safe='')}.bamboohr.com/careers/list"

    def _detail_url(self, source: SourceConfig, external_id: str) -> str:
        return (
            f"https://{quote(source.tenant, safe='')}.bamboohr.com/careers/"
            f"{quote(external_id, safe='')}/detail"
        )

    def _max_jobs(self, source: SourceConfig) -> int:
        raw = source.options.get("max_jobs", 100)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid BambooHR max_jobs: {raw!r}") from exc
        if value < 1:
            raise ValueError("BambooHR max_jobs must be at least 1")
        return value

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._list_url(source))
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("BambooHR response is not valid JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("result"), list):
            raise InvalidResponseError("BambooHR response must contain a result array")

        postings = data["result"]
        max_jobs = self._max_jobs(source)
        selected = postings[:max_jobs]
        raw_jobs: list[dict[str, Any]] = []
        payloads: list[Any] = [data]
        request_urls = [str(response.url)]
        detail_failures = 0
        limit_reason = "max_jobs_reached" if len(postings) > len(selected) else None

        for item in selected:
            if not isinstance(item, dict):
                raw_jobs.append({"raw": item})
                continue
            raw = dict(item)
            external_id = non_empty_str(raw.get("id"))
            if external_id is not None:
                try:
                    detail_response = self.http.get(
                        self._detail_url(source, external_id)
                    )
                    detail_data = detail_response.json()
                    if isinstance(detail_data, dict):
                        detail = detail_data.get("result")
                        if isinstance(detail, dict):
                            opening = detail.get("jobOpening")
                            if isinstance(opening, dict):
                                raw["_detail"] = opening
                    request_urls.append(str(detail_response.url))
                    payloads.append(detail_data)
                except (HttpError, ValueError):
                    detail_failures += 1
            raw_jobs.append(raw)

        complete = limit_reason is None and detail_failures == 0
        batch = FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://{quote(source.tenant, safe='')}.bamboohr.com/careers",
            pagination={
                "total": len(postings),
                "returned": len(raw_jobs),
                "detail_failures": detail_failures,
                "complete": complete,
                **({"limit_reason": limit_reason} if limit_reason else {}),
            },
            complete=complete,
            raw_payloads=payloads,
        )
        if not complete:
            reason = limit_reason or "detail_fetch_failed"
            raise PartialFetchError(f"BambooHR fetch incomplete: {reason}", batch)
        return batch

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("BambooHR job must be an object")
        detail = raw_job.get("_detail")
        detail = detail if isinstance(detail, dict) else {}

        external_id = non_empty_str(raw_job.get("id"))
        title = non_empty_str(raw_job.get("jobOpeningName")) or non_empty_str(
            detail.get("jobOpeningName")
        )
        if external_id is None or title is None:
            raise InvalidResponseError("BambooHR job is missing id or jobOpeningName")

        source_url = non_empty_str(detail.get("jobOpeningShareUrl")) or (
            f"https://{quote(source.tenant, safe='')}.bamboohr.com/careers/{external_id}"
        )
        location = self._location(raw_job, detail)
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=external_id,
            title=title,
            company=source.company,
            description=non_empty_str(detail.get("description")),
            location=location,
            source_url=source_url,
            application_url=source_url,
            salary=non_empty_str(detail.get("compensation")),
            employment_type=normalize_employment_type(
                detail.get("employmentType") or raw_job.get("employmentType")
            ),
            remote_status=normalize_remote_status(
                "remote" if raw_job.get("isRemote") is True or detail.get("isRemote") is True else None,
                location,
            ),
            original_posted_at=non_empty_str(detail.get("datePosted")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _location(raw_job: dict[str, Any], detail: dict[str, Any]) -> str | None:
        for value in (detail.get("location"), raw_job.get("location")):
            if isinstance(value, dict):
                parts = [
                    non_empty_str(value.get("city")),
                    non_empty_str(value.get("state")),
                    non_empty_str(value.get("addressCountry")),
                ]
                text = ", ".join(part for part in parts if part)
                if text:
                    return text
        for value in (detail.get("atsLocation"), raw_job.get("atsLocation")):
            if isinstance(value, dict):
                parts = [
                    non_empty_str(value.get("city")),
                    non_empty_str(value.get("state")),
                    non_empty_str(value.get("country")),
                ]
                text = ", ".join(part for part in parts if part)
                if text:
                    return text
        return None
