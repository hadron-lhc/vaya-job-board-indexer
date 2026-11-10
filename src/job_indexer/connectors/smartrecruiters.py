from __future__ import annotations

import html
from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import (
    format_salary,
    non_empty_str,
    normalize_employment_type,
    normalize_remote_status,
    to_utc_iso,
)


class SmartRecruitersConnector:
    platform = "smartrecruiters"
    _MAX_PAGES = 100

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _page_size(self, source: SourceConfig) -> int:
        raw = source.options.get("page_size", 100)
        try:
            page_size = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid SmartRecruiters page_size: {raw!r}") from exc
        if page_size < 1 or page_size > 100:
            raise ValueError("SmartRecruiters page_size must be between 1 and 100")
        return page_size

    def _list_url(self, source: SourceConfig) -> str:
        company = quote(source.tenant, safe="")
        return f"https://api.smartrecruiters.com/v1/companies/{company}/postings"

    def _detail_url(self, source: SourceConfig, external_id: str) -> str:
        company = quote(source.tenant, safe="")
        job_id = quote(external_id, safe="")
        return (
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}"
        )

    def _fallback_source_url(self, source: SourceConfig, external_id: str) -> str:
        company = quote(source.tenant, safe="")
        job_id = quote(external_id, safe="")
        return f"https://jobs.smartrecruiters.com/{company}/{job_id}"

    def _batch(
        self,
        *,
        source: SourceConfig,
        raw_jobs: list[dict[str, Any]],
        request_urls: list[str],
        payloads: list[Any],
        page_size: int,
        pages: int,
        total: int,
        detail_requests: int,
        detail_failures: int,
        complete: bool,
        limit_reason: str | None = None,
    ) -> FetchBatch:
        pagination: dict[str, Any] = {
            "page_size": page_size,
            "pages": pages,
            "returned": len(raw_jobs),
            "total": total,
            "detail_requests": detail_requests,
            "detail_failures": detail_failures,
            "complete": complete,
        }
        if limit_reason is not None:
            pagination["limit_reason"] = limit_reason
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://jobs.smartrecruiters.com/{quote(source.tenant, safe='')}",
            pagination=pagination,
            complete=complete,
            raw_payloads=payloads,
        )

    def fetch(self, source: SourceConfig) -> FetchBatch:
        list_url = self._list_url(source)
        page_size = self._page_size(source)

        postings: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_urls: list[str] = []
        offset = 0
        pages = 0
        total: int | None = None

        while True:
            try:
                response = self.http.get(
                    list_url,
                    params={"limit": page_size, "offset": offset},
                )
            except HttpError as exc:
                if postings:
                    raise PartialFetchError(
                        str(exc),
                        self._batch(
                            source=source,
                            raw_jobs=postings,
                            request_urls=request_urls,
                            payloads=payloads,
                            page_size=page_size,
                            pages=pages,
                            total=total if total is not None else len(postings),
                            detail_requests=0,
                            detail_failures=0,
                            complete=False,
                        ),
                    ) from exc
                raise

            try:
                data = response.json()
            except ValueError as exc:
                if postings:
                    raise PartialFetchError(
                        f"SmartRecruiters response is not valid JSON after {pages} page(s): {exc}",
                        self._batch(
                            source=source,
                            raw_jobs=postings,
                            request_urls=request_urls,
                            payloads=payloads,
                            page_size=page_size,
                            pages=pages,
                            total=total if total is not None else len(postings),
                            detail_requests=0,
                            detail_failures=0,
                            complete=False,
                        ),
                    ) from exc
                raise InvalidResponseError(
                    "SmartRecruiters response is not valid JSON"
                ) from exc

            if not isinstance(data, dict) or not isinstance(data.get("content"), list):
                if postings:
                    raise PartialFetchError(
                        "SmartRecruiters response must contain a content array",
                        self._batch(
                            source=source,
                            raw_jobs=postings,
                            request_urls=request_urls,
                            payloads=payloads,
                            page_size=page_size,
                            pages=pages,
                            total=total if total is not None else len(postings),
                            detail_requests=0,
                            detail_failures=0,
                            complete=False,
                        ),
                    )
                raise InvalidResponseError(
                    "SmartRecruiters response must contain a content array"
                )

            content = data["content"]
            if any(not isinstance(item, dict) for item in content):
                raise InvalidResponseError(
                    "SmartRecruiters content entries must be objects"
                )

            total_value = data.get("totalFound")
            if isinstance(total_value, int) and not isinstance(total_value, bool):
                total = total_value

            postings.extend(content)
            payloads.append(data)
            request_urls.append(str(response.url))
            pages += 1
            offset += len(content)

            if not content:
                break
            if total is not None and offset >= total:
                break
            if len(content) < page_size:
                break
            if pages >= self._MAX_PAGES:
                raise PartialFetchError(
                    "SmartRecruiters pagination exceeded 100 pages",
                    self._batch(
                        source=source,
                        raw_jobs=postings,
                        request_urls=request_urls,
                        payloads=payloads,
                        page_size=page_size,
                        pages=pages,
                        total=total if total is not None else len(postings),
                        detail_requests=0,
                        detail_failures=0,
                        complete=False,
                        limit_reason="max_pages_reached",
                    ),
                )

        raw_jobs = [dict(posting) for posting in postings]
        detail_requests = 0
        detail_failures = 0

        for index, posting in enumerate(raw_jobs):
            external_id = posting.get("id")
            if external_id is None:
                raise InvalidResponseError(
                    "SmartRecruiters posting is missing id"
                )
            detail_url = self._detail_url(source, str(external_id))
            try:
                response = self.http.get(detail_url)
            except HttpError as exc:
                detail_failures += 1
                raise PartialFetchError(
                    str(exc),
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        page_size=page_size,
                        pages=pages,
                        total=total if total is not None else len(postings),
                        detail_requests=detail_requests,
                        detail_failures=detail_failures,
                        complete=False,
                    ),
                ) from exc

            try:
                detail = response.json()
            except ValueError as exc:
                detail_failures += 1
                raise PartialFetchError(
                    f"SmartRecruiters detail response is not valid JSON: {exc}",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        page_size=page_size,
                        pages=pages,
                        total=total if total is not None else len(postings),
                        detail_requests=detail_requests,
                        detail_failures=detail_failures,
                        complete=False,
                    ),
                ) from exc

            if not isinstance(detail, dict):
                detail_failures += 1
                raise PartialFetchError(
                    "SmartRecruiters detail response must be an object",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        page_size=page_size,
                        pages=pages,
                        total=total if total is not None else len(postings),
                        detail_requests=detail_requests,
                        detail_failures=detail_failures,
                        complete=False,
                    ),
                )

            raw_jobs[index] = {**posting, **detail}
            payloads.append(detail)
            request_urls.append(str(response.url))
            detail_requests += 1

        return self._batch(
            source=source,
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            payloads=payloads,
            page_size=page_size,
            pages=pages,
            total=total if total is not None else len(postings),
            detail_requests=detail_requests,
            detail_failures=detail_failures,
            complete=True,
        )

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("SmartRecruiters job must be an object")

        external_id = raw_job.get("id")
        title = non_empty_str(raw_job.get("name"))
        if external_id is None or title is None:
            raise InvalidResponseError(
                "SmartRecruiters job is missing id or name"
            )

        source_url = non_empty_str(raw_job.get("postingUrl")) or (
            self._fallback_source_url(source, str(external_id))
        )
        company = self._company(raw_job, source)
        location = self._location(raw_job)
        explicit_remote = self._remote_flag(raw_job)
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=company,
            description=self._description(raw_job),
            location=location,
            source_url=source_url,
            application_url=non_empty_str(raw_job.get("applyUrl")),
            salary=format_salary(raw_job.get("compensation")),
            employment_type=self._employment_type(raw_job),
            remote_status=normalize_remote_status(explicit_remote, location),
            original_posted_at=non_empty_str(raw_job.get("releasedDate")),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )

    @staticmethod
    def _company(raw_job: dict[str, Any], source: SourceConfig) -> str:
        company = raw_job.get("company")
        if isinstance(company, dict):
            return non_empty_str(company.get("name")) or source.company
        if isinstance(company, str):
            return non_empty_str(company) or source.company
        return source.company

    @staticmethod
    def _location(raw_job: dict[str, Any]) -> str | None:
        location = raw_job.get("location")
        if not isinstance(location, dict):
            return None
        full_location = non_empty_str(location.get("fullLocation"))
        if full_location is not None:
            return full_location
        parts = [
            non_empty_str(location.get("city")),
            non_empty_str(location.get("region")),
            non_empty_str(location.get("country")),
        ]
        text = ", ".join(part for part in parts if part)
        return text or None

    @staticmethod
    def _remote_flag(raw_job: dict[str, Any]) -> str | None:
        location = raw_job.get("location")
        if not isinstance(location, dict):
            return None
        if location.get("remote") is True:
            return "remote"
        if location.get("hybrid") is True:
            return "hybrid"
        return None

    @staticmethod
    def _employment_type(raw_job: dict[str, Any]) -> str | None:
        employment = raw_job.get("typeOfEmployment")
        if isinstance(employment, dict):
            return normalize_employment_type(employment.get("label"))
        return normalize_employment_type(employment)

    @staticmethod
    def _description(raw_job: dict[str, Any]) -> str | None:
        job_ad = raw_job.get("jobAd")
        if not isinstance(job_ad, dict):
            return None
        sections = job_ad.get("sections")
        if not isinstance(sections, dict):
            return None

        parts: list[str] = []
        for section in sections.values():
            if not isinstance(section, dict):
                continue
            text = section.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            title = non_empty_str(section.get("title"))
            if title is not None:
                parts.append(f"<h2>{html.escape(title)}</h2>\n{text.strip()}")
            else:
                parts.append(text.strip())
        return "\n".join(parts) or None
