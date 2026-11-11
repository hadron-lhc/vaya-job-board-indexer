from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..errors import HttpError, InvalidResponseError, PartialFetchError
from ..http import HttpClient
from ..models import FetchBatch, JobListing, SourceConfig
from ..utils import non_empty_str, normalize_employment_type, normalize_remote_status, to_utc_iso


class WorkdayConnector:
    platform = "workday"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _host(self, source: SourceConfig) -> str:
        value = non_empty_str(source.options.get("host")) or non_empty_str(source.base_url)
        if value is None:
            raise ValueError("Workday source requires options.host")
        return value.removeprefix("https://").removeprefix("http://").rstrip("/")

    def _site(self, source: SourceConfig) -> str:
        value = non_empty_str(source.options.get("site"))
        if value is None:
            raise ValueError("Workday source requires options.site")
        return value.strip("/")

    def _list_url(self, source: SourceConfig) -> str:
        return f"https://{self._host(source)}/wday/cxs/{quote(source.tenant, safe='')}/{quote(self._site(source), safe='')}/jobs"

    def _detail_url(self, source: SourceConfig, external_path: str) -> str:
        path = external_path if external_path.startswith("/") else f"/{external_path}"
        return (
            f"https://{self._host(source)}/wday/cxs/{quote(source.tenant, safe='')}/"
            f"{quote(self._site(source), safe='')}{path}"
        )

    def _max_jobs(self, source: SourceConfig) -> int:
        raw = source.options.get("max_jobs", 500)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid Workday max_jobs: {raw!r}") from exc
        if value < 1:
            raise ValueError("Workday max_jobs must be >= 1")
        return value

    def _batch(
        self,
        *,
        source: SourceConfig,
        raw_jobs: list[dict[str, Any]],
        request_urls: list[str],
        payloads: list[Any],
        total: int | None,
        pages: int,
        complete: bool,
        limit_reason: str | None = None,
    ) -> FetchBatch:
        pagination: dict[str, Any] = {
            "pages": pages,
            "returned": len(raw_jobs),
            "total_items": total,
            "complete": complete,
        }
        if limit_reason is not None:
            pagination["limit_reason"] = limit_reason
        return FetchBatch(
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            source_url=f"https://{self._host(source)}/en-US/{quote(self._site(source), safe='')}",
            pagination=pagination,
            complete=complete,
            raw_payloads=payloads,
        )

    def fetch(self, source: SourceConfig) -> FetchBatch:
        list_url = self._list_url(source)
        max_jobs = self._max_jobs(source)
        limit = 20
        offset = 0
        total: int | None = None
        raw_jobs: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_urls: list[str] = []
        pages = 0
        truncated = False

        while True:
            body = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": "",
            }
            try:
                response = self.http.post(list_url, json=body)
            except HttpError as exc:
                if raw_jobs:
                    raise PartialFetchError(
                        str(exc),
                        self._batch(
                            source=source,
                            raw_jobs=[dict(job) for job in raw_jobs],
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total,
                            pages=pages,
                            complete=False,
                        ),
                    ) from exc
                raise

            try:
                data = response.json()
            except ValueError as exc:
                if raw_jobs:
                    raise PartialFetchError(
                        f"Workday response is not valid JSON: {exc}",
                        self._batch(
                            source=source,
                            raw_jobs=[dict(job) for job in raw_jobs],
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total,
                            pages=pages,
                            complete=False,
                        ),
                    ) from exc
                raise InvalidResponseError("Workday response is not valid JSON") from exc

            if not isinstance(data, dict) or not isinstance(data.get("jobPostings"), list):
                if raw_jobs:
                    raise PartialFetchError(
                        "Workday response must contain a jobPostings array",
                        self._batch(
                            source=source,
                            raw_jobs=[dict(job) for job in raw_jobs],
                            request_urls=request_urls,
                            payloads=payloads,
                            total=total,
                            pages=pages,
                            complete=False,
                        ),
                    )
                raise InvalidResponseError("Workday response must contain a jobPostings array")

            postings = data["jobPostings"]
            if any(not isinstance(item, dict) for item in postings):
                raise InvalidResponseError("Workday job postings must be objects")

            total_value = data.get("total")
            if isinstance(total_value, int) and not isinstance(total_value, bool):
                total = total_value

            remaining = max_jobs - len(raw_jobs)
            if remaining <= 0:
                truncated = True
                break
            raw_jobs.extend(postings[:remaining])
            if len(postings) > remaining:
                truncated = True
            payloads.append(data)
            request_urls.append(str(response.url))
            pages += 1
            offset += len(postings)

            if not postings:
                break
            if total is not None and len(raw_jobs) >= total:
                break
            if len(raw_jobs) >= max_jobs:
                truncated = total is None or total > max_jobs
                break
            if len(postings) < limit:
                break

        complete = not truncated
        limit_reason = "max_jobs_reached" if truncated else None

        for index, item in enumerate(raw_jobs):
            external_path = non_empty_str(item.get("externalPath"))
            if external_path is None:
                raise PartialFetchError(
                    "Workday job posting is missing externalPath",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        total=total,
                        pages=pages,
                        complete=False,
                    ),
                )
            try:
                response = self.http.get(self._detail_url(source, external_path))
            except HttpError as exc:
                raise PartialFetchError(
                    str(exc),
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        total=total,
                        pages=pages,
                        complete=False,
                    ),
                ) from exc
            try:
                detail = response.json()
            except ValueError as exc:
                raise PartialFetchError(
                    f"Workday detail response is not valid JSON: {exc}",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        total=total,
                        pages=pages,
                        complete=False,
                    ),
                ) from exc
            if not isinstance(detail, dict) or not isinstance(detail.get("jobPostingInfo"), dict):
                raise PartialFetchError(
                    "Workday detail response must contain jobPostingInfo",
                    self._batch(
                        source=source,
                        raw_jobs=raw_jobs,
                        request_urls=request_urls,
                        payloads=payloads,
                        total=total,
                        pages=pages,
                        complete=False,
                    ),
                )
            raw_jobs[index] = {**item, "detail": detail}
            payloads.append(detail)
            request_urls.append(str(response.url))

        batch = self._batch(
            source=source,
            raw_jobs=raw_jobs,
            request_urls=request_urls,
            payloads=payloads,
            total=total,
            pages=pages,
            complete=complete,
            limit_reason=limit_reason,
        )
        if not complete:
            raise PartialFetchError(
                f"Workday fetch truncated: {limit_reason}",
                batch,
            )
        return batch

    def normalize(
        self,
        raw_job: dict[str, Any],
        source: SourceConfig,
        checked_at: datetime,
    ) -> JobListing:
        if not isinstance(raw_job, dict):
            raise InvalidResponseError("Workday job posting must be an object")

        detail = raw_job.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        info = detail.get("jobPostingInfo")
        if not isinstance(info, dict):
            info = {}

        external_path = non_empty_str(raw_job.get("externalPath"))
        external_id = (
            non_empty_str(info.get("jobReqId"))
            or non_empty_str(info.get("jobPostingId"))
            or external_path
        )
        title = non_empty_str(info.get("title")) or non_empty_str(raw_job.get("title"))
        if external_id is None or title is None:
            raise InvalidResponseError("Workday job posting is missing id or title")

        source_url = non_empty_str(info.get("externalUrl"))
        if source_url is None and external_path is not None:
            path = external_path if external_path.startswith("/") else f"/{external_path}"
            source_url = f"https://{self._host(source)}/en-US/{quote(self._site(source), safe='')}{path}"
        if source_url is None:
            raise InvalidResponseError("Workday job posting is missing externalUrl")

        location = (
            non_empty_str(info.get("location"))
            or non_empty_str(raw_job.get("locationsText"))
        )
        hiring_organization = detail.get("hiringOrganization")
        company = source.company
        if isinstance(hiring_organization, dict):
            company = non_empty_str(hiring_organization.get("name")) or company
        checked_iso = to_utc_iso(checked_at)

        return JobListing(
            platform=self.platform,
            source_instance=source.name,
            external_job_id=str(external_id),
            title=title,
            company=company,
            description=non_empty_str(info.get("jobDescription")),
            location=location,
            source_url=source_url,
            application_url=source_url,
            salary=None,
            employment_type=normalize_employment_type(info.get("timeType")),
            remote_status=normalize_remote_status(info.get("remoteType"), location),
            original_posted_at=(
                non_empty_str(info.get("startDate"))
                or non_empty_str(raw_job.get("postedOn"))
            ),
            first_seen_at=checked_iso,
            last_checked_at=checked_iso,
        )
