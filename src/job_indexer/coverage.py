from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .db import get_source_status, get_job_count


DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[2] / "docs" / "platform_matrix.csv"

PLATFORM_KEYS = {
    "Greenhouse": "greenhouse",
    "Lever.co": "lever",
    "Ashby": "ashby",
    "Workable": "workable",
    "SmartRecruiters": "smartrecruiters",
    "Recruitee": "recruitee",
    "Personio": "personio",
    "Teamtailor": "teamtailor",
    "Pinpoint": "pinpoint",
    "Rippling": "rippling",
    "Workday": "workday",
}

ACTIVE_STATUSES = {
    "IMPLEMENTED",
    "FIXTURE_TESTED",
    "LIVE_TESTED_ONE_TENANT",
    "LIVE_TESTED_MULTI_TENANT",
    "VERIFIED",
}


def load_matrix(path: str | Path | None = None) -> list[dict[str, str]]:
    matrix_path = Path(path) if path is not None else DEFAULT_MATRIX_PATH
    with matrix_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_coverage(
    conn,
    *,
    matrix_path: str | Path | None = None,
) -> dict[str, Any]:
    rows = load_matrix(matrix_path)
    sources = get_source_status(conn)
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        by_platform.setdefault(source["platform"], []).append(source)

    platforms: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in rows:
        platform_key = PLATFORM_KEYS.get(row["platform"])
        platform_sources = by_platform.get(platform_key, []) if platform_key else []
        successful = [
            source for source in platform_sources if source["last_success_at"] is not None
        ]
        status = row["implementation_status"]
        if platform_key and len(successful) >= 2 and status in ACTIVE_STATUSES:
            status = "LIVE_TESTED_MULTI_TENANT"
        elif platform_key and successful and status in ACTIVE_STATUSES:
            status = "LIVE_TESTED_ONE_TENANT"
        elif platform_key and platform_sources and status in ACTIVE_STATUSES:
            status = "IMPLEMENTED"
        counts[status] = counts.get(status, 0) + 1
        platforms.append(
            {
                "platform": row["platform"],
                "platform_key": platform_key,
                "category": row["category"],
                "extraction_method": row["extraction_method"],
                "authentication": row["authentication"],
                "implementation_status": status,
                "matrix_status": row["implementation_status"],
                "confidence": row["confidence"],
                "known_limitations": row["known_limitations"],
                "evidence_url": row["evidence_url"],
                "source_instances": len(platform_sources),
                "successful_sources": len(successful),
                "jobs": sum(int(source["job_count"] or 0) for source in platform_sources),
                "last_success_at": max(
                    (source["last_success_at"] for source in successful),
                    default=None,
                ),
            }
        )

    return {
        "total_required": len(rows),
        "categories": {
            "ATS": sum(1 for row in rows if row["category"] == "ATS"),
            "Job Board": sum(1 for row in rows if row["category"] == "Job Board"),
        },
        "status_counts": dict(sorted(counts.items())),
        "implemented_platforms": sorted(
            {
                platform["platform_key"]
                for platform in platforms
                if platform["platform_key"]
                and platform["implementation_status"] in ACTIVE_STATUSES
            }
        ),
        "live_multi_tenant_platforms": sorted(
            {
                platform["platform_key"]
                for platform in platforms
                if platform["implementation_status"] == "LIVE_TESTED_MULTI_TENANT"
            }
        ),
        "source_instances": len(sources),
        "total_jobs": get_job_count(conn),
        "platforms": platforms,
    }
