from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .api import serve
from .config import load_sources
from .connectors.registry import SUPPORTED_PLATFORMS, build_connector
from .coverage import (
    build_coverage,
    build_coverage_checklist,
    render_coverage_checklist_markdown,
)
from .db import connect, init_db, rebuild_dedup
from .http import HttpClient
from .runner import run_fetch
from .scheduler import run_schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-indexer",
        description="Multi-tenant job board indexer with search API and UI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch and persist one source instance.")
    fetch_parser.add_argument("--platform", required=True, choices=SUPPORTED_PLATFORMS)
    fetch_parser.add_argument("--source", required=True, help="Source instance name from config.")
    fetch_parser.add_argument("--config", default="config/sources.json")
    fetch_parser.add_argument("--db", default="data/jobs.db")
    fetch_parser.add_argument("--artifacts-dir", default="artifacts")

    all_parser = subparsers.add_parser("fetch-all", help="Refresh every configured source.")
    all_parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS)
    all_parser.add_argument("--source", action="append", default=None)
    all_parser.add_argument("--config", default="config/sources.json")
    all_parser.add_argument("--db", default="data/jobs.db")
    all_parser.add_argument("--artifacts-dir", default="artifacts")
    all_parser.add_argument("--json", action="store_true", help="Print full JSON results.")

    schedule_parser = subparsers.add_parser(
        "schedule",
        help="Refresh sources on a recurring interval until stopped.",
    )
    schedule_parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS)
    schedule_parser.add_argument("--source", action="append", default=None)
    schedule_parser.add_argument("--config", default="config/sources.json")
    schedule_parser.add_argument("--db", default="data/jobs.db")
    schedule_parser.add_argument("--artifacts-dir", default="artifacts")
    schedule_parser.add_argument("--interval-minutes", type=float, default=60.0)
    schedule_parser.add_argument(
        "--no-immediate",
        action="store_true",
        help="Wait one interval before the first refresh.",
    )
    schedule_parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Stop after N cycles (useful for smoke tests).",
    )

    list_parser = subparsers.add_parser("list-sources", help="List configured source instances.")
    list_parser.add_argument("--config", default="config/sources.json")

    coverage_parser = subparsers.add_parser("coverage", help="Print platform coverage JSON.")
    coverage_parser.add_argument("--db", default="data/jobs.db")
    coverage_parser.add_argument("--matrix", default=None)

    checklist_parser = subparsers.add_parser(
        "coverage-checklist",
        help="Generate the 78-platform coverage checklist and evidence report.",
    )
    checklist_parser.add_argument("--db", default="data/jobs.db")
    checklist_parser.add_argument("--matrix", default=None)
    checklist_parser.add_argument("--evidence-dir", default="artifacts/live_runs")
    checklist_parser.add_argument("--output", default="docs/coverage_checklist.md")
    checklist_parser.add_argument(
        "--json-output",
        default="artifacts/coverage/checklist.json",
    )

    dedupe_parser = subparsers.add_parser("rebuild-dedup", help="Rebuild canonical jobs from listings.")
    dedupe_parser.add_argument("--db", default="data/jobs.db")

    serve_parser = subparsers.add_parser("serve", help="Start the HTTP API and search UI.")
    serve_parser.add_argument("--db", default="data/jobs.db")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--matrix", default=None)

    return parser


def _exit_code(results: list[Any]) -> int:
    statuses = {result.status for result in results}
    if "FAILED" in statuses or any(
        status
        in {"RATE_LIMITED", "UNAUTHORIZED", "BLOCKED", "TIMEOUT", "SCHEMA_CHANGED"}
        for status in statuses
    ):
        return 1
    if "PARTIAL_SUCCESS" in statuses:
        return 2
    return 0


def _select_sources(
    sources: dict[str, Any],
    *,
    platform: str | None = None,
    names: list[str] | None = None,
) -> list[Any]:
    selected = list(sources.values())
    if platform:
        selected = [source for source in selected if source.platform == platform]
    if names:
        requested = set(names)
        missing = requested - set(sources)
        if missing:
            raise ValueError(f"source(s) not configured: {', '.join(sorted(missing))}")
        selected = [source for source in selected if source.name in requested]
    if not selected:
        raise ValueError("no sources selected")
    return selected


def _run_sources(
    selected: list[Any],
    *,
    db_path: str,
    artifacts_dir: str,
) -> list[Any]:
    results = []
    with HttpClient() as http:
        for source in selected:
            connector = build_connector(source.platform, http)
            result = run_fetch(
                source,
                connector,
                db_path=db_path,
                artifacts_dir=artifacts_dir,
            )
            results.append(result)
            print(
                f"{result.source.name}\t{result.status}\t"
                f"{result.jobs_processed}/{result.jobs_discovered}\t"
                f"+{result.jobs_inserted} ~{result.jobs_updated} "
                f"!{result.jobs_changed} -{result.jobs_closed}",
                file=sys.stderr,
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"coverage", "coverage-checklist", "rebuild-dedup", "serve"}:
        if args.command == "serve":
            serve(
                args.db,
                host=args.host,
                port=args.port,
                matrix_path=args.matrix,
            )
            return 0
        conn = connect(args.db)
        init_db(conn)
        try:
            if args.command == "coverage":
                print(
                    json.dumps(
                        build_coverage(conn, matrix_path=args.matrix),
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            elif args.command == "coverage-checklist":
                checklist = build_coverage_checklist(
                    conn,
                    matrix_path=args.matrix,
                    evidence_dir=args.evidence_dir,
                )
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    render_coverage_checklist_markdown(checklist),
                    encoding="utf-8",
                )
                json_path = Path(args.json_output)
                json_path.parent.mkdir(parents=True, exist_ok=True)
                json_path.write_text(
                    json.dumps(checklist, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                print(
                    f"Wrote {output_path} and {json_path} "
                    f"({len(checklist['platforms'])} platforms)."
                )
            else:
                count = rebuild_dedup(conn)
                print(f"Rebuilt {count} canonical job(s).")
        finally:
            conn.close()
        return 0

    try:
        sources = load_sources(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "list-sources":
        for source in sources.values():
            print(f"{source.name}\t{source.platform}\t{source.tenant}\t{source.company}")
        return 0

    if args.command in {"fetch-all", "schedule"}:
        try:
            selected = _select_sources(
                sources,
                platform=args.platform,
                names=args.source,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.command == "fetch-all":
            results = _run_sources(
                selected,
                db_path=args.db,
                artifacts_dir=args.artifacts_dir,
            )
            payload = [result.to_dict() for result in results]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return _exit_code(results)

        interval_seconds = args.interval_minutes * 60.0
        last_exit_code = 0

        def cycle() -> list[Any]:
            nonlocal last_exit_code
            results = _run_sources(
                selected,
                db_path=args.db,
                artifacts_dir=args.artifacts_dir,
            )
            last_exit_code = _exit_code(results)
            return results

        def report(run_number: int, results: list[Any]) -> None:
            print(
                f"cycle={run_number} sources={len(results)} "
                f"statuses={','.join(result.status for result in results)}",
                file=sys.stderr,
            )

        try:
            run_schedule(
                cycle,
                interval_seconds,
                run_immediately=not args.no_immediate,
                max_runs=args.max_runs,
                on_cycle=report,
            )
        except KeyboardInterrupt:
            print("scheduler stopped", file=sys.stderr)
        return last_exit_code

    source = sources.get(args.source)
    if source is None:
        print(f"error: source {args.source!r} is not configured", file=sys.stderr)
        return 1
    if source.platform != args.platform:
        print(
            f"error: source {source.name!r} is platform {source.platform!r}, "
            f"not {args.platform!r}",
            file=sys.stderr,
        )
        return 1

    with HttpClient() as http:
        connector = build_connector(source.platform, http)
        result = run_fetch(
            source,
            connector,
            db_path=args.db,
            artifacts_dir=args.artifacts_dir,
        )

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return _exit_code([result])
