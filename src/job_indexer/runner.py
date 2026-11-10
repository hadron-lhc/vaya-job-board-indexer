from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connectors.base import Connector
from .db import (
    connect,
    create_fetch_run,
    finish_fetch_run,
    init_db,
    upsert_jobs,
    upsert_source_instance,
)
from .errors import PartialFetchError
from .models import FetchBatch, FetchResult, JobListing, SourceConfig
from .utils import utc_now_iso


def _save_raw_payloads(
    artifacts_dir: str | Path,
    source: SourceConfig,
    run_id: str,
    payloads: list[Any],
) -> str | None:
    if not payloads:
        return None
    path = Path(artifacts_dir) / "raw" / source.name / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source_instance": source.name,
                "platform": source.platform,
                "tenant": source.tenant,
                "run_id": run_id,
                "saved_at": utc_now_iso(),
                "payloads": payloads,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def _normalize_batch(
    connector: Connector,
    batch: FetchBatch,
    source: SourceConfig,
    checked_at: datetime,
) -> list[JobListing]:
    return [connector.normalize(raw_job, source, checked_at) for raw_job in batch.raw_jobs]


def _fields_available(jobs: list[JobListing]) -> list[str]:
    fields: set[str] = set()
    for job in jobs:
        for key, value in job.as_dict().items():
            if value is not None:
                fields.add(key)
    return sorted(fields)


def run_fetch(
    source: SourceConfig,
    connector: Connector,
    db_path: str | Path = "data/jobs.db",
    artifacts_dir: str | Path = "artifacts",
    checked_at: datetime | None = None,
) -> FetchResult:
    run_id = uuid.uuid4().hex
    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    checked_at = checked_at or datetime.now(timezone.utc)
    conn = connect(db_path)
    init_db(conn)
    upsert_source_instance(conn, source)
    create_fetch_run(conn, run_id=run_id, source=source, started_at=started_at)

    batch: FetchBatch | None = None
    raw_payload_path: str | None = None
    jobs: list[JobListing] = []
    inserted = 0
    updated = 0
    status = "failed"
    error: str | None = None

    try:
        try:
            batch = connector.fetch(source)
            status = "success"
        except PartialFetchError as exc:
            batch = exc.batch
            error = str(exc)
            status = "partial"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "failed"

        if batch is not None:
            raw_payload_path = _save_raw_payloads(
                artifacts_dir, source, run_id, batch.raw_payloads
            )
            jobs = _normalize_batch(connector, batch, source, checked_at)
            inserted, updated = upsert_jobs(conn, jobs)
    except Exception as exc:
        conn.rollback()
        detail = f"{type(exc).__name__}: {exc}"
        error = f"{error}; {detail}" if error else detail
        status = "failed"
    finally:
        completed_at = utc_now_iso()
        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        pagination = batch.pagination if batch is not None else {}
        jobs_discovered = len(batch.raw_jobs) if batch is not None else 0
        jobs_processed = len(jobs)

        try:
            finish_fetch_run(
                conn,
                run_id=run_id,
                completed_at=completed_at,
                status=status,
                jobs_discovered=jobs_discovered,
                jobs_processed=jobs_processed,
                jobs_inserted=inserted,
                jobs_updated=updated,
                error_details=error,
                duration_ms=duration_ms,
                raw_payload_path=raw_payload_path,
                pagination=pagination,
            )
        finally:
            conn.close()

    return FetchResult(
        run_id=run_id,
        source=source,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        jobs_discovered=jobs_discovered,
        jobs_processed=jobs_processed,
        jobs_inserted=inserted,
        jobs_updated=updated,
        error=error,
        duration_ms=duration_ms,
        request_urls=batch.request_urls if batch is not None else [],
        source_url=batch.source_url if batch is not None else None,
        pagination=pagination,
        raw_payload_path=raw_payload_path,
        fields_available=_fields_available(jobs),
        samples=[job.as_dict() for job in jobs[:3]],
    )
