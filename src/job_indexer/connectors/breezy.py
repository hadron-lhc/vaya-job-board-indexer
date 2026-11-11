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
from .jsonld import (
    find_job_posting,
    job_posting_company,
    job_posting_description,
    job_posting_employment_type,
    job_posting_location,
    job_posting_posted_at,
    job_posting_remote_status,
    job_posting_salary,
    job_posting_title,
)


class BreezyConnector:
    platform = "breezy"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _board_url(self, source: SourceConfig) -> str:
        return f"https://{quote(source.tenant, safe='')}.breezy.hr/json"

    def _max_jobs(self, source: SourceConfig) -> int:
        raw = source.options.get("max_jobs", 50)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Breezy max_jobs: {raw!r}") from exc
        if value < 1:
            raise ValueError("Breezy max_jobs must be at least 1")
        return value

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._board_url(source))
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Breezy response is not valid JSON") from exc
        if not isinstance(data, list):
            raise InvalidResponseError("Breezy response must be a JSON array")

        max_jobs = self._max_jobs(source)
        selected = data[:max_jobs]
        raw_jobs: list[dict[str, Any]] = []
        payloads: list[Any] = [data]
        request_urls = [str(response.url)]
        detail_failures = 0
        limit_reason = "max_jobs_reached" if len(data) > len(selected) else None

        for item in selected:
            if not isinstance(item, dict):
                raw_jobs.append({"raw": item})
                continue
            raw = dict(item)
            detail_url = non_empty_str(raw.get("url"))
            if detail_url:
                try:
                    detail_response = self.http.get(
                        detail_url,
                        headers={"Accept": "text/html,application/xhtml+xml"},
                    )
                    posting = find_job_posting(detail_response.text)
                    if posting is not None:
                        raw["_jsonld"] = posting
                    request_urls.append(str(detail_response.url))
                    payloads.append(detail_response.text)
                except HttpError:
                    detail_failures += 1
            raw_jobs.append(raw)

        complete = limit_reason is None and detail_failures == 0
        batch = FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://{quote(source.tenant, safe='')}.breezy.hr/",
            pagination={
                "total": len(data),
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
            raise PartialFetchError(f"Breezy fetch incomplete: {reason}", batch)
        return batch

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Breezy job must be an object")
        posting = raw_job.get("_jsonld")
        posting = posting if isinstance(posting, dict) else {}

        external_id = non_empty_str(raw_job.get("friendly_id")) or non_empty_str(
            raw_job.get("id")
        )
        title = non_empty_str(raw_job.get("name")) or job_posting_title(posting)
        source_url = non_empty_str(raw_job.get("url"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Breezy job is missing id, name, or url")

        location = self._location(raw_job) or job_posting_location(posting)
        remote_status = self._remote_status(raw_job, posting, location)
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=external_id,
            title=title,
            company=job_posting_company(posting) or source.company,
            description=job_posting_description(posting),
            location=location,
            source_url=source_url,
            application_url=source_url,
            salary=non_empty_str(raw_job.get("salary")) or job_posting_salary(posting),
            employment_type=normalize_employment_type(
                self._employment_type(raw_job) or job_posting_employment_type(posting)
            ),
            remote_status=normalize_remote_status(remote_status, location),
            original_posted_at=non_empty_str(raw_job.get("published_date"))
            or job_posting_posted_at(posting),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        locations = raw_job.get("locations")
        labels: list[str] = []
        if isinstance(locations, list):
            for location in locations:
                if isinstance(location, dict):
                    label = non_empty_str(location.get("name"))
                    if label and label not in labels:
                        labels.append(label)
        if labels:
            return "; ".join(labels)
        location = raw_job.get("location")
        if isinstance(location, dict):
            return non_empty_str(location.get("name"))
        return non_empty_str(location)

    @staticmethod
    def _remote_status(
        raw_job: dict[str, Any],
        posting: dict[str, Any],
        location: str | None,
    ) -> str | None:
        posting_status = job_posting_remote_status(posting, location)
        if posting_status is not None:
            return posting_status
        locations = raw_job.get("locations")
        if isinstance(locations, list):
            for location_value in locations:
                if not isinstance(location_value, dict):
                    continue
                details = location_value.get("remote_details")
                if isinstance(details, dict):
                    label = str(details.get("label", "")).lower()
                    value = str(details.get("value", "")).lower()
                    if "hybrid" in label or value == "hybrid":
                        return "hybrid"
                if location_value.get("is_remote") is True:
                    return "remote"
        location_value = raw_job.get("location")
        if isinstance(location_value, dict):
            details = location_value.get("remote_details")
            if isinstance(details, dict):
                label = str(details.get("label", "")).lower()
                value = str(details.get("value", "")).lower()
                if "hybrid" in label or value == "hybrid":
                    return "hybrid"
            if location_value.get("is_remote") is True:
                return "remote"
        return None

    @staticmethod
    def _employment_type(raw_job: dict[str, Any]) -> str | None:
        value = raw_job.get("type")
        if isinstance(value, dict):
            return non_empty_str(value.get("name")) or non_empty_str(value.get("id"))
        return non_empty_str(value)
