from __future__ import annotations

import json
import os
from pathlib import Path

from .connectors.registry import SUPPORTED_PLATFORMS
from .models import SourceConfig


DEFAULT_SOURCES_PATH = Path("config/sources.json")


def load_sources(path: str | Path | None = None) -> dict[str, SourceConfig]:
    configured_path = path or os.environ.get("JOB_INDEXER_SOURCES") or DEFAULT_SOURCES_PATH
    config_path = Path(configured_path)
    if not config_path.exists():
        raise FileNotFoundError(f"source configuration not found: {config_path}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in source configuration: {config_path}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError("source configuration must contain a top-level 'sources' array")

    sources: dict[str, SourceConfig] = {}
    for item in data["sources"]:
        source = SourceConfig.from_dict(item)
        if source.name in sources:
            raise ValueError(f"duplicate source name: {source.name!r}")
        if source.platform not in SUPPORTED_PLATFORMS:
            raise ValueError(
                f"source {source.name!r} uses unsupported platform {source.platform!r}"
            )
        sources[source.name] = source

    return sources
