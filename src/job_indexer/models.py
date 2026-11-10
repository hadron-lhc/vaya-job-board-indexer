from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REMOTE_STATUSES = frozenset({"remote", "hybrid", "onsite", "unknown"})


@dataclass(frozen=True)
class SourceConfig:
    """A configured employer instance for one supported platform."""

    name: str
    platform: str
    tenant: str
    company: str
    options: dict[str, Any] = field(default_factory=dict)
    base_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceConfig":
        if not isinstance(data, dict):
            raise ValueError("source configuration must be an object")

        required = ("name", "platform", "tenant", "company")
        for key in required:
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"source configuration field {key!r} must be a non-empty string")

        options = data.get("options", {})
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise ValueError("source configuration field 'options' must be an object")

        base_url = data.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError("source configuration field 'base_url' must be a string or null")

        return cls(
            name=data["name"].strip(),
            platform=data["platform"].strip(),
            tenant=data["tenant"].strip(),
            company=data["company"].strip(),
            options=dict(options),
            base_url=base_url.strip() if isinstance(base_url, str) else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "platform": self.platform,
            "tenant": self.tenant,
            "company": self.company,
            "options": dict(self.options),
            "base_url": self.base_url,
        }


@dataclass(frozen=True)
class JobListing:
    """Normalized source-level listing. No cross-source merging happens yet."""

    platform: str
    source_instance: str
    external_job_id: str
    title: str
    company: str
    description: str | None
    location: str | None
    source_url: str
    application_url: str | None
    salary: str | None
    employment_type: str | None
    remote_status: str
    original_posted_at: str | None
    first_seen_at: str
    last_checked_at: str

    def __post_init__(self) -> None:
        if self.remote_status not in REMOTE_STATUSES:
            raise ValueError(f"unsupported remote_status: {self.remote_status!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "source_instance": self.source_instance,
            "external_job_id": self.external_job_id,
            "title": self.title,
            "company": self.company,
            "description": self.description,
            "location": self.location,
            "source_url": self.source_url,
            "application_url": self.application_url,
            "salary": self.salary,
            "employment_type": self.employment_type,
            "remote_status": self.remote_status,
            "original_posted_at": self.original_posted_at,
            "first_seen_at": self.first_seen_at,
            "last_checked_at": self.last_checked_at,
        }


@dataclass
class FetchBatch:
    """Raw jobs and request metadata returned by a connector fetch."""

    raw_jobs: list[dict[str, Any]]
    request_urls: list[str]
    source_url: str
    pagination: dict[str, Any] = field(default_factory=dict)
    complete: bool = True
    raw_payloads: list[Any] = field(default_factory=list)


@dataclass
class FetchResult:
    """Outcome of one connector fetch and persistence run."""

    run_id: str
    source: SourceConfig
    status: str
    started_at: str
    completed_at: str
    jobs_discovered: int
    jobs_processed: int
    jobs_inserted: int
    jobs_updated: int
    jobs_changed: int
    jobs_missing: int
    jobs_closed: int
    error: str | None
    error_class: str | None
    duration_ms: int
    request_urls: list[str]
    source_url: str | None
    pagination: dict[str, Any]
    raw_payload_path: str | None
    fields_available: list[str]
    samples: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "platform": self.source.platform,
            "source_instance": self.source.name,
            "employer": self.source.company,
            "tenant": self.source.tenant,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "source_url": self.source_url,
            "request_urls": list(self.request_urls),
            "pagination": dict(self.pagination),
            "jobs_discovered": self.jobs_discovered,
            "jobs_processed": self.jobs_processed,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "jobs_changed": self.jobs_changed,
            "jobs_missing": self.jobs_missing,
            "jobs_closed": self.jobs_closed,
            "error": self.error,
            "error_class": self.error_class,
            "raw_payload_path": self.raw_payload_path,
            "fields_available": list(self.fields_available),
            "samples": list(self.samples),
        }
