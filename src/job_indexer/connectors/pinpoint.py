from __future__ import annotations

import re
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
    to_utc_iso,
)


UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class PinpointConnector:
    platform = "pinpoint"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _postings_url(self, source: SourceConfig) -> str:
        subdomain = quote(source.tenant, safe="")
        return f"https://{subdomain}.pinpointhq.com/postings.json"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._postings_url(source))
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Pinpoint response is not valid JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise InvalidResponseError("Pinpoint response must contain a data array")

        postings = data["data"]
        return FetchBatch(
            raw_jobs=postings,
            request_urls=[str(response.url)],
            source_url=f"https://{quote(source.tenant, safe='')}.pinpointhq.com/",
            pagination={
                "total": len(postings),
                "returned": len(postings),
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
            raise InvalidResponseError("Pinpoint posting must be an object")

        title = non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("url"))
        if title is None or source_url is None:
            raise InvalidResponseError("Pinpoint posting is missing title or url")

        external_id = self._external_id(raw_job, source_url)
        location = self._location(raw_job)
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=external_id,
            title=title,
            company=source.company,
            description=self._description(raw_job),
            location=location,
            source_url=source_url,
            application_url=source_url,
            salary=self._salary(raw_job),
            employment_type=normalize_employment_type(
                raw_job.get("employment_type_text") or raw_job.get("employment_type")
            ),
            remote_status=normalize_remote_status(
                raw_job.get("workplace_type_text") or raw_job.get("workplace_type"),
                location,
            ),
            original_posted_at=None,
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _external_id(raw_job: dict[str, Any], source_url: str) -> str:
        match = UUID_RE.search(source_url)
        if match:
            return match.group(0)
        value = raw_job.get("id")
        if value is None:
            raise InvalidResponseError("Pinpoint posting is missing id")
        return str(value)

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        location = raw_job.get("location")
        if not isinstance(location, dict):
            return None
        name = non_empty_str(location.get("name"))
        if name is not None:
            return name
        parts = [
            non_empty_str(location.get("city")),
            non_empty_str(location.get("province")),
        ]
        text = ", ".join(part for part in parts if part)
        return text or None

    @staticmethod
    def _description(raw_job: dict[str, Any]) -> str | None:
        parts: list[str] = []
        sections = (
            ("description", None),
            ("key_responsibilities", "key_responsibilities_header"),
            ("skills_knowledge_expertise", "skills_knowledge_expertise_header"),
            ("benefits", "benefits_header"),
        )
        for field, header_field in sections:
            text = non_empty_str(raw_job.get(field))
            if text is None:
                continue
            header = non_empty_str(raw_job.get(header_field)) if header_field else None
            if header is not None:
                parts.append(f"<h2>{header}</h2>\n{text}")
            else:
                parts.append(text)
        return "\n".join(parts) or None

    @staticmethod
    def _salary(raw_job: dict[str, Any]) -> str | None:
        if raw_job.get("compensation_visible") is not True:
            return None
        summary = non_empty_str(raw_job.get("compensation"))
        if summary is not None:
            return summary
        minimum = raw_job.get("compensation_minimum")
        maximum = raw_job.get("compensation_maximum")
        if minimum is None and maximum is None:
            return None
        return format_salary(
            {
                "min": minimum,
                "max": maximum,
                "currency": raw_job.get("compensation_currency"),
                "interval": raw_job.get("compensation_frequency"),
            }
        )
