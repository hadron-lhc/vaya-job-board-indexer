from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import InvalidResponseError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    to_utc_iso,
)


class WorkableConnector:
    platform = "workable"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _jobs_url(self, source: SourceConfig) -> str:
        subdomain = quote(source.tenant, safe="")
        return f"https://apply.workable.com/api/v1/widget/accounts/{subdomain}"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._jobs_url(source), params={"details": "true"})
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Workable response is not valid JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise InvalidResponseError("Workable response must contain a jobs array")

        raw_jobs = self._merge_duplicate_shortcodes(data["jobs"])
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=[str(response.url)],
            source_url=f"https://apply.workable.com/{quote(source.tenant, safe='')}",
            pagination={
                "total": len(data["jobs"]),
                "returned": len(raw_jobs),
                "duplicate_postings": len(data["jobs"]) - len(raw_jobs),
                "pagination_required": False,
            },
            complete=True,
            raw_payloads=[data],
        )

    @staticmethod
    def _merge_duplicate_shortcodes(jobs: list[Any]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        positions: dict[str, int] = {}

        for item in jobs:
            if not isinstance(item, dict):
                merged.append(item)
                continue
            shortcode = non_empty_str(item.get("shortcode"))
            if shortcode is None or shortcode not in positions:
                if shortcode is not None:
                    positions[shortcode] = len(merged)
                merged.append(dict(item))
                continue

            existing = merged[positions[shortcode]]
            incoming_locations = item.get("locations")
            if not isinstance(incoming_locations, list):
                continue
            existing_locations = existing.get("locations")
            if not isinstance(existing_locations, list):
                existing_locations = []
                existing["locations"] = existing_locations

            seen = {
                (
                    non_empty_str(location.get("city")),
                    non_empty_str(location.get("region")),
                    non_empty_str(location.get("country")),
                )
                for location in existing_locations
                if isinstance(location, dict)
            }
            for location in incoming_locations:
                if not isinstance(location, dict):
                    continue
                key = (
                    non_empty_str(location.get("city")),
                    non_empty_str(location.get("region")),
                    non_empty_str(location.get("country")),
                )
                if key not in seen:
                    existing_locations.append(location)
                    seen.add(key)

        return merged

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Workable job must be an object")

        external_id = non_empty_str(raw_job.get("shortcode"))
        title = non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("url")) or non_empty_str(
            raw_job.get("shortlink")
        )
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Workable job is missing shortcode, title, or url")

        location = self._location(raw_job)
        explicit_remote = "remote" if raw_job.get("telecommuting") is True else None
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=external_id,
            title=title,
            company=source.company,
            description=non_empty_str(raw_job.get("description")),
            location=location,
            source_url=source_url,
            application_url=non_empty_str(raw_job.get("application_url")),
            salary=None,
            employment_type=normalize_employment_type(raw_job.get("employment_type")),
            remote_status=normalize_remote_status(explicit_remote, location),
            original_posted_at=non_empty_str(raw_job.get("published_on"))
            or non_empty_str(raw_job.get("created_at")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        locations = raw_job.get("locations")
        if isinstance(locations, list):
            formatted: list[str] = []
            for item in locations:
                if not isinstance(item, dict):
                    continue
                parts = [
                    non_empty_str(item.get("city")),
                    non_empty_str(item.get("region")),
                    non_empty_str(item.get("country")),
                ]
                text = ", ".join(part for part in parts if part)
                if text and text not in formatted:
                    formatted.append(text)
            if formatted:
                return "; ".join(formatted)

        parts = [
            non_empty_str(raw_job.get("city")),
            non_empty_str(raw_job.get("state")),
            non_empty_str(raw_job.get("country")),
        ]
        text = ", ".join(part for part in parts if part)
        return text or None
