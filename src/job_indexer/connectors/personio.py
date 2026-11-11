from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

from ..errors import InvalidResponseError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    to_utc_iso,
)


class PersonioConnector:
    platform = "personio"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _feed_url(self, source: SourceConfig) -> str:
        subdomain = quote(source.tenant, safe="")
        return f"https://{subdomain}.jobs.personio.de/xml?language=en"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(
            self._feed_url(source),
            headers={"Accept": "application/xml, text/xml"},
        )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise InvalidResponseError("Personio response is not valid XML") from exc
        if root.tag != "workzag-jobs":
            raise InvalidResponseError("Personio XML root must be workzag-jobs")

        raw_jobs = [self._position_to_dict(position) for position in root.findall("position")]
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=[str(response.url)],
            source_url=f"https://{quote(source.tenant, safe='')}.jobs.personio.de/",
            pagination={
                "total": len(raw_jobs),
                "returned": len(raw_jobs),
                "pagination_required": False,
            },
            complete=True,
            raw_payloads=[response.text],
        )

    @staticmethod
    def _position_to_dict(position: ET.Element) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for child in position:
            if child.tag == "jobDescriptions":
                descriptions: list[dict[str, str | None]] = []
                for description in child.findall("jobDescription"):
                    descriptions.append(
                        {
                            "name": non_empty_str(description.findtext("name")),
                            "value": non_empty_str(description.findtext("value")),
                        }
                    )
                data["jobDescriptions"] = descriptions
            else:
                data[child.tag] = non_empty_str(child.text)
        return data

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Personio position must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("name"))
        if external_id is None or title is None:
            raise InvalidResponseError("Personio position is missing id or name")

        source_url = (
            f"https://{quote(source.tenant, safe='')}.jobs.personio.de/job/"
            f"{quote(str(external_id), safe='')}?language=en"
        )
        location = non_empty_str(raw_job.get("office"))
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=non_empty_str(raw_job.get("subcompany")) or source.company,
            description=self._description(raw_job),
            location=location,
            source_url=source_url,
            application_url=None,
            salary=None,
            employment_type=normalize_employment_type(
                raw_job.get("schedule") or raw_job.get("employmentType")
            ),
            remote_status=normalize_remote_status(None, location),
            original_posted_at=non_empty_str(raw_job.get("createdAt")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _description(raw_job: dict[str, Any]) -> str | None:
        descriptions = raw_job.get("jobDescriptions")
        if not isinstance(descriptions, list):
            return None
        parts: list[str] = []
        for description in descriptions:
            if not isinstance(description, dict):
                continue
            value = non_empty_str(description.get("value"))
            if value is None:
                continue
            name = non_empty_str(description.get("name"))
            if name is not None:
                parts.append(f"<h2>{name}</h2>\n{value}")
            else:
                parts.append(value)
        return "\n".join(parts) or None
