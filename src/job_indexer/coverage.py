from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .db import get_source_status, get_job_count
from .utils import utc_now_iso


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
    "Breezy HR": "breezy",
    "BambooHR": "bamboohr",
    "JazzHR": "jazzhr",
    "Niceboard": "niceboard",
}

ACTIVE_STATUSES = {
    "IMPLEMENTED",
    "FIXTURE_TESTED",
    "LIVE_TESTED_ONE_TENANT",
    "LIVE_TESTED_MULTI_TENANT",
    "VERIFIED",
}

STATUS_RANK = {
    "NOT_RESEARCHED": 0,
    "RESEARCHED": 1,
    "ACCESS_BLOCKED": 1,
    "IMPLEMENTED": 2,
    "FIXTURE_TESTED": 3,
    "LIVE_TESTED_ONE_TENANT": 4,
    "LIVE_TESTED_MULTI_TENANT": 5,
    "VERIFIED": 6,
}


def _stronger(left: str, right: str) -> str:
    return left if STATUS_RANK.get(left, 0) >= STATUS_RANK.get(right, 0) else right


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
        evidenced = [
            source
            for source in platform_sources
            if source.get("last_evidence_at") is not None
        ]
        status = row["implementation_status"]
        if platform_key and len(evidenced) >= 2:
            status = _stronger(status, "LIVE_TESTED_MULTI_TENANT")
        elif platform_key and evidenced:
            status = _stronger(status, "LIVE_TESTED_ONE_TENANT")
        elif platform_key and platform_sources:
            status = _stronger(status, "IMPLEMENTED")
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
                "evidenced_sources": len(evidenced),
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
                if platform["platform_key"]
                and platform["implementation_status"] == "LIVE_TESTED_MULTI_TENANT"
            }
        ),
        "source_instances": len(sources),
        "total_jobs": get_job_count(conn),
        "platforms": platforms,
    }


def _coverage_state(status: str) -> str:
    if status == "LIVE_TESTED_MULTI_TENANT":
        return "live_multi_tenant"
    if status == "LIVE_TESTED_ONE_TENANT":
        return "live_one_tenant"
    if status in {"IMPLEMENTED", "FIXTURE_TESTED"}:
        return "implemented"
    if status == "VERIFIED":
        return "verified"
    if status == "ACCESS_BLOCKED":
        return "blocked"
    if status == "NOT_RESEARCHED":
        return "not_researched"
    return "research_only"


def build_coverage_checklist(
    conn,
    *,
    matrix_path: str | Path | None = None,
    evidence_dir: str | Path | None = None,
) -> dict[str, Any]:
    coverage = build_coverage(conn, matrix_path=matrix_path)
    sources = get_source_status(conn)
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        by_platform.setdefault(source["platform"], []).append(source)

    evidence_root = Path(evidence_dir) if evidence_dir is not None else None
    platforms: list[dict[str, Any]] = []
    for platform in coverage["platforms"]:
        platform_key = platform["platform_key"]
        platform_sources = by_platform.get(platform_key, []) if platform_key else []
        evidence_paths: list[str] = []
        if evidence_root is not None:
            for source in platform_sources:
                path = evidence_root / f"{source['name']}.json"
                if path.exists():
                    evidence_paths.append(str(path))
        missing: list[str] = []
        if not platform_key:
            missing.append("connector")
        if platform_sources and not any(
            source.get("last_evidence_at") is not None for source in platform_sources
        ):
            missing.append("live_evidence")
        if len(platform_sources) < 2:
            missing.append("second_tenant")
        if platform["implementation_status"] == "RESEARCHED":
            missing.append("live_endpoint_verification")
        if platform["implementation_status"] == "ACCESS_BLOCKED":
            missing.append("access")
        if platform["implementation_status"] == "NOT_RESEARCHED":
            missing.append("product_identity")
        platforms.append(
            {
                **platform,
                "coverage_state": _coverage_state(platform["implementation_status"]),
                "configured_sources": [source["name"] for source in platform_sources],
                "live_statuses": {
                    source["name"]: source.get("last_status") for source in platform_sources
                },
                "last_evidence_at": max(
                    (
                        source["last_evidence_at"]
                        for source in platform_sources
                        if source.get("last_evidence_at") is not None
                    ),
                    default=None,
                ),
                "evidence_paths": evidence_paths,
                "missing_requirements": missing,
            }
        )

    return {
        "generated_at": utc_now_iso(),
        "total_required": coverage["total_required"],
        "categories": coverage["categories"],
        "status_counts": coverage["status_counts"],
        "source_instances": coverage["source_instances"],
        "total_jobs": coverage["total_jobs"],
        "platforms": platforms,
    }


def render_coverage_checklist_markdown(checklist: dict[str, Any]) -> str:
    lines = [
        "# Coverage Checklist",
        "",
        f"Generated: {checklist['generated_at']}",
        "",
        "Source of truth: `docs/platform_matrix.csv`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total platforms | {checklist['total_required']} |",
        f"| ATS platforms | {checklist['categories']['ATS']} |",
        f"| Job-board platforms | {checklist['categories']['Job Board']} |",
        f"| Configured sources | {checklist['source_instances']} |",
        f"| Indexed jobs | {checklist['total_jobs']} |",
        "",
        "## Status counts",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status, count in sorted(checklist["status_counts"].items()):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Full checklist",
            "",
            "| Platform | Category | Status | Sources | Evidenced | Jobs | Missing | Evidence |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for platform in checklist["platforms"]:
        missing = ", ".join(platform["missing_requirements"]) or "none"
        evidence = platform["evidence_url"] or "none"
        if platform["evidence_paths"]:
            evidence = f"{evidence}<br>`{platform['evidence_paths'][0]}`"
        lines.append(
            "| {platform} | {category} | `{status}` | {sources} | {evidenced} | {jobs} | {missing} | {evidence} |".format(
                platform=platform["platform"],
                category=platform["category"],
                status=platform["implementation_status"],
                sources=platform["source_instances"],
                evidenced=platform["evidenced_sources"],
                jobs=platform["jobs"],
                missing=missing,
                evidence=evidence,
            )
        )
    lines.append("")
    return "\n".join(lines)
