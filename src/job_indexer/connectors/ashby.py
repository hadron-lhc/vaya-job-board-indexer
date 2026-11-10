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
    to_utc_iso,
)


class AshbyConnector:
    platform = "ashby"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _jobs_url(self, source: SourceConfig) -> str:
        org = quote(source.tenant, safe="")
        return f"https://api.ashbyhq.com/posting-api/job-board/{org}"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(
            self._jobs_url(source),
            params={"includeCompensation": "true"},
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Ashby response is not valid JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise InvalidResponseError("Ashby response must contain a jobs array")

        jobs = data["jobs"]
        return FetchBatch(
            raw_jobs=jobs,
            request_urls=[str(response.url)],
            source_url=f"https://jobs.ashbyhq.com/{quote(source.tenant, safe='')}",
            pagination={
                "total": len(jobs),
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
            raise InvalidResponseError("Ashby job must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("jobUrl"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("Ashby job is missing id, title, or jobUrl")

        location = non_empty_str(raw_job.get("location"))
        description = non_empty_str(raw_job.get("descriptionHtml")) or non_empty_str(
            raw_job.get("descriptionPlain")
        )

        explicit_remote = raw_job.get("workplaceType")
        if non_empty_str(explicit_remote) is None and raw_job.get("isRemote") is True:
            explicit_remote = "remote"

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
            salary=self._salary(raw_job.get("compensation")),
            employment_type=normalize_employment_type(raw_job.get("employmentType")),
            remote_status=normalize_remote_status(explicit_remote, location),
            original_posted_at=non_empty_str(raw_job.get("publishedAt")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _salary(value: Any) -> str | None:
        if isinstance(value, dict):
            summary = non_empty_str(
                value.get("scrapeableCompensationSalarySummary")
            ) or non_empty_str(value.get("compensationTierSummary"))
            if summary is not None:
                return summary
        return format_salary(value)
