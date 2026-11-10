from __future__ import annotations

import argparse
import json
import sys

from .config import load_sources
from .connectors.registry import SUPPORTED_PLATFORMS, build_connector
from .http import HttpClient
from .runner import run_fetch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-indexer",
        description="Minimal multi-tenant job board indexer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch and persist one source instance.")
    fetch_parser.add_argument("--platform", required=True, choices=SUPPORTED_PLATFORMS)
    fetch_parser.add_argument("--source", required=True, help="Source instance name from config.")
    fetch_parser.add_argument("--config", default="config/sources.json")
    fetch_parser.add_argument("--db", default="data/jobs.db")
    fetch_parser.add_argument("--artifacts-dir", default="artifacts")

    list_parser = subparsers.add_parser("list-sources", help="List configured source instances.")
    list_parser.add_argument("--config", default="config/sources.json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        sources = load_sources(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "list-sources":
        for source in sources.values():
            print(f"{source.name}\t{source.platform}\t{source.tenant}\t{source.company}")
        return 0

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
    if result.status == "success":
        return 0
    if result.status == "partial":
        return 2
    return 1
