from __future__ import annotations

import html
from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import InvalidResponseError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import non_empty_str, normalize_remote_status, to_utc_iso


class GreenhouseConnector:
    platform = "greenhouse"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _jobs_url(self, source: SourceConfig) -> str:
        token = quote(source.tenant, safe="")
        return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(self._jobs_url(source), params={"content": "true"})
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Greenhouse response is not valid JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise InvalidResponseError("Greenhouse response must contain a jobs array")

        jobs = data["jobs"]
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        total = meta.get("total")
        return FetchBatch(
            raw_jobs=jobs,
            request_urls=[str(response.url)],
            source_url=f"https://boards.greenhouse.io/{quote(source.tenant, safe='')}",
            pagination={
                "total": total if isinstance(total, int) else len(jobs),
                "returned": len(jobs),
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
            raise InvalidResponseError("Greenhouse job must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("absolute_url"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Greenhouse job is missing id, title, or absolute_url")

        company = non_empty_str(raw_job.get("company_name")) or source.company

        location_value = raw_job.get("location")
        location: str | None = None
        if isinstance(location_value, dict):
            location = non_empty_str(location_value.get("name"))
        elif isinstance(location_value, str):
            location = non_empty_str(location_value)

        description_value = raw_job.get("content")
        description = html.unescape(description_value) if isinstance(description_value, str) else None
        if description is not None:
            description = description.strip() or None

        checked_iso = to_utc_iso(checked_at)
        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=company,
            description=description,
            location=location,
            source_url=source_url,
            application_url=None,
            salary=None,
            employment_type=None,
            remote_status=normalize_remote_status(None, location),
            original_posted_at=non_empty_str(raw_job.get("first_published")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )
