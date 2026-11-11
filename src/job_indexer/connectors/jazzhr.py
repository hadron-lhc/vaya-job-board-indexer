from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    html_to_text,
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


LINK_RE = re.compile(
    r"<a\b[^>]*href=[\"']([^\"']*/apply/jobs/details/[^\"']+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
JOB_ID_RE = re.compile(r"/apply/jobs/details/([^/?#]+)")


class JazzHRConnector:
    platform = "jazzhr"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _list_url(self, source: SourceConfig) -> str:
        return f"https://{quote(source.tenant, safe='')}.applytojob.com/apply/jobs"

    def _max_jobs(self, source: SourceConfig) -> int:
        raw = source.options.get("max_jobs", 100)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid JazzHR max_jobs: {raw!r}") from exc
        if value < 1:
            raise ValueError("JazzHR max_jobs must be at least 1")
        return value

    def fetch(self, source: SourceConfig) -> FetchBatch:
        response = self.http.get(
            self._list_url(source),
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        links = self._extract_links(response.text, str(response.url))
        max_jobs = self._max_jobs(source)
        selected = links[:max_jobs]
        raw_jobs: list[dict[str, Any]] = []
        payloads: list[Any] = [response.text]
        request_urls = [str(response.url)]
        detail_failures = 0
        limit_reason = "max_jobs_reached" if len(links) > len(selected) else None

        for job_id, detail_url, link_title in selected:
            raw: dict[str, Any] = {
                "id": job_id,
                "url": detail_url,
                "title": link_title,
            }
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
            source_url=f"https://{quote(source.tenant, safe='')}.applytojob.com/apply",
            pagination={
                "total": len(links),
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
            raise PartialFetchError(f"JazzHR fetch incomplete: {reason}", batch)
        return batch

    @staticmethod
    def _extract_links(text: str, base_url: str) -> list[tuple[str, str, str | None]]:
        links: list[tuple[str, str, str | None]] = []
        seen: set[str] = set()
        for match in LINK_RE.finditer(text):
            href = match.group(1).strip()
            job_match = JOB_ID_RE.search(href)
            if job_match is None:
                continue
            job_id = job_match.group(1)
            if job_id in seen:
                continue
            seen.add(job_id)
            title = html_to_text(match.group(2)) or None
            url = urljoin(base_url, href)
            parsed = urlparse(url)
            url = parsed._replace(query="", fragment="").geturl()
            links.append((job_id, url, title))
        return links

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("JazzHR job must be an object")
        posting = raw_job.get("_jsonld")
        posting = posting if isinstance(posting, dict) else {}

        external_id = non_empty_str(raw_job.get("id"))
        title = job_posting_title(posting) or non_empty_str(raw_job.get("title"))
        source_url = non_empty_str(raw_job.get("url"))
        if external_id is None or title is None or source_url is None:
            raise InvalidResponseError("JazzHR job is missing id, title, or url")

        location = job_posting_location(posting)
        remote_status = job_posting_remote_status(posting, location)
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
            salary=job_posting_salary(posting),
            employment_type=normalize_employment_type(
                job_posting_employment_type(posting)
            ),
            remote_status=normalize_remote_status(remote_status, location),
            original_posted_at=job_posting_posted_at(posting),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )
