from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import InvalidResponseError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    format_salary,
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    parse_recruitee_datetime,
    to_utc_iso,
)


class RecruiteeConnector:
    platform = "recruitee"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _offers_url(self, source: SourceConfig) -> str:
        subdomain = quote(source.tenant, safe="")
        return f"https://{subdomain}.recruitee.com/api/offers/"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._offers_url(source))
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Recruitee response is not valid JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
            raise InvalidResponseError("Recruitee response must contain an offers array")

        offers = data["offers"]
        return FetchBatch(
            raw_jobs=offers,
            request_urls=[str(response.url)],
            source_url=f"https://{quote(source.tenant, safe='')}.recruitee.com/",
            pagination={
                "total": len(offers),
                "returned": len(offers),
                "pagination_required": False,
            },
            complete=True,
            raw_payloads=[data],
        )

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Recruitee offer must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("title"))
        if external_id is None or title is None:
            raise InvalidResponseError("Recruitee offer is missing id or title")

        source_url = non_empty_str(raw_job.get("careers_url")) or self._fallback_url(
            source, raw_job
        )
        description = self._description(raw_job)
        location = self._location(raw_job)
        checked_iso = to_utc_iso(checked_at)
        company = non_empty_str(raw_job.get("company_name")) or source.company

        explicit_remote: str | None = None
        if raw_job.get("remote") is True:
            explicit_remote = "remote"
        elif raw_job.get("hybrid") is True:
            explicit_remote = "hybrid"
        elif raw_job.get("on_site") is True:
            explicit_remote = "onsite"

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=company,
            description=description,
            location=location,
            source_url=source_url,
            application_url=non_empty_str(raw_job.get("careers_apply_url")),
            salary=self._salary(raw_job.get("salary")),
            employment_type=normalize_employment_type(raw_job.get("employment_type_code")),
            remote_status=normalize_remote_status(explicit_remote, location),
            original_posted_at=parse_recruitee_datetime(raw_job.get("published_at")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _description(raw_job: dict[str, Any]) -> str | None:
        parts = [
            non_empty_str(raw_job.get("description")),
            non_empty_str(raw_job.get("requirements")),
        ]
        return "\n".join(part for part in parts if part) or None

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        locations = raw_job.get("locations")
        labels: list[str] = []
        if isinstance(locations, list):
            for location in locations:
                if not isinstance(location, dict):
                    continue
                label = non_empty_str(location.get("name"))
                if label is None:
                    parts = [
                        non_empty_str(location.get("city")),
                        non_empty_str(location.get("state")),
                        non_empty_str(location.get("country")),
                    ]
                    label = ", ".join(part for part in parts if part) or None
                if label and label not in labels:
                    labels.append(label)
        if labels:
            return "; ".join(labels)
        return non_empty_str(raw_job.get("location"))

    @staticmethod
    def _salary(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        minimum = value.get("min")
        maximum = value.get("max")
        if minimum in (None, "", "0", 0) and maximum in (None, "", "0", 0):
            return None
        return format_salary(value)

    @staticmethod
    def _fallback_url(source: SourceConfig, raw_job: dict[str, Any]) -> str:
        slug = non_empty_str(raw_job.get("slug")) or str(raw_job.get("id"))
        return f"https://{quote(source.tenant, safe='')}.recruitee.com/o/{quote(slug, safe='')}"
