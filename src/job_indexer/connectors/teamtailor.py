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
    normalize_remote_status,
    parse_rfc822_datetime,
    to_utc_iso,
)


TT_LOCATIONS = "{https://teamtailor.com/locations}locations"
TT_LOCATION = "{https://teamtailor.com/locations}location"
TT_DEPARTMENT = "{https://teamtailor.com/locations}department"


class TeamtailorConnector:
    platform = "teamtailor"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _feed_url(self, source: SourceConfig) -> str:
        subdomain = quote(source.tenant, safe="")
        return f"https://{subdomain}.teamtailor.com/jobs.rss"

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(
            self._feed_url(source),
            headers={"Accept": "application/rss+xml, application/xml, text/xml"},
        )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise InvalidResponseError("Teamtailor response is not valid RSS/XML") from exc
        if root.tag != "rss":
            raise InvalidResponseError("Teamtailor XML root must be rss")
        channel = root.find("channel")
        if channel is None:
            raise InvalidResponseError("Teamtailor RSS feed is missing channel")

        raw_jobs = [self._item_to_dict(item) for item in channel.findall("item")]
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=[str(response.url)],
            source_url=f"https://{quote(source.tenant, safe='')}.teamtailor.com/jobs",
            pagination={
                "total": len(raw_jobs),
                "returned": len(raw_jobs),
                "pagination_required": False,
                "note": "RSS feeds may cap at 100 items.",
            },
            complete=True,
            raw_payloads=[response.text],
        )

    @staticmethod
    def _item_to_dict(item: ET.Element) -> dict[str, Any]:
        locations: list[dict[str, str | None]] = []
        for location in item.findall(f"{TT_LOCATIONS}/{TT_LOCATION}"):
            locations.append(
                {
                    "name": non_empty_str(location.findtext("{https://teamtailor.com/locations}name")),
                    "city": non_empty_str(location.findtext("{https://teamtailor.com/locations}city")),
                    "country": non_empty_str(location.findtext("{https://teamtailor.com/locations}country")),
                }
            )
        return {
            "title": non_empty_str(item.findtext("title")),
            "description": non_empty_str(item.findtext("description")),
            "pubDate": non_empty_str(item.findtext("pubDate")),
            "link": non_empty_str(item.findtext("link")),
            "remoteStatus": non_empty_str(item.findtext("remoteStatus")),
            "guid": non_empty_str(item.findtext("guid")),
            "locations": locations,
            "department": non_empty_str(item.findtext(TT_DEPARTMENT)),
        }

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Teamtailor item must be an object")

        title = non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("link"))
        if title is None or source_url is None:
            raise InvalidResponseError("Teamtailor item is missing title or link")

        external_id = non_empty_str(raw_job.get("guid")) or source_url
        remote_status = raw_job.get("remoteStatus")
        explicit_remote = {
            "fully": "remote",
            "temporary": "remote",
            "hybrid": "hybrid",
            "none": "onsite",
        }.get(str(remote_status).lower()) if remote_status else None
        location = self._location(raw_job.get("locations"))
        if location is None and explicit_remote == "remote":
            location = "Remote"
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
            application_url=source_url,
            salary=None,
            employment_type=None,
            remote_status=normalize_remote_status(explicit_remote, location),
            original_posted_at=parse_rfc822_datetime(raw_job.get("pubDate")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _location(value: Any) -> str | None:
        if not isinstance(value, list):
            return non_empty_str(value)
        labels: list[str] = []
        for location in value:
            if not isinstance(location, dict):
                continue
            name = non_empty_str(location.get("name"))
            if name is None:
                parts = [
                    non_empty_str(location.get("city")),
                    non_empty_str(location.get("country")),
                ]
                name = ", ".join(part for part in parts if part) or None
            if name and name not in labels:
                labels.append(name)
        return "; ".join(labels) or None
