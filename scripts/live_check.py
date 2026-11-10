from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from job_indexer.config import load_sources
from job_indexer.connectors.registry import build_connector
from job_indexer.http import HttpClient
from job_indexer.runner import run_fetch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live checks for configured job sources.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "sources.json")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "jobs.db")
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "artifacts" / "live_runs")
    parser.add_argument("--source", action="append", dest="sources")
    return parser.parse_args()


def compact_result(result) -> dict:
    payload = result.to_dict()
    for sample in payload.get("samples", []):
        description = sample.get("description")
        if description and len(description) > 500:
            sample["description"] = description[:500] + "...[truncated]"
    return payload


def main() -> int:
    args = parse_args()
    sources = load_sources(args.config)
    selected = args.sources or list(sources)
    missing = [name for name in selected if name not in sources]
    if missing:
        print(f"Unknown sources: {', '.join(missing)}", file=sys.stderr)
        return 2

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "config": str(args.config),
        "sources": {},
    }
    failed = False

    with HttpClient() as http:
        for name in selected:
            source = sources[name]
            connector = build_connector(source.platform, http)
            result = run_fetch(
                source,
                connector,
                db_path=args.db,
                artifacts_dir=args.artifacts_dir,
            )
            evidence = compact_result(result)
            evidence_path = args.evidence_dir / f"{name}.json"
            evidence_path.write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            summary["sources"][name] = {
                "platform": source.platform,
                "tenant": source.tenant,
                "employer": source.company,
                "status": result.status,
                "jobs_discovered": result.jobs_discovered,
                "jobs_processed": result.jobs_processed,
                "jobs_inserted": result.jobs_inserted,
                "jobs_updated": result.jobs_updated,
                "pagination": result.pagination,
                "request_urls": result.request_urls,
                "raw_payload_path": result.raw_payload_path,
                "evidence_path": str(evidence_path),
                "error": result.error,
            }
            print(
                f"{name}: {result.status} "
                f"discovered={result.jobs_discovered} "
                f"processed={result.jobs_processed} "
                f"inserted={result.jobs_inserted} "
                f"updated={result.jobs_updated}"
            )
            if result.status != "success":
                failed = True

    summary_path = args.evidence_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Evidence: {summary_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
