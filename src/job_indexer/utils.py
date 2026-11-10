from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def normalize_employment_type(value: Any) -> str | None:
    text = non_empty_str(value)
    if text is None:
        return None
    key = text.lower().replace("_", "").replace("-", "").replace(" ", "")
    known = {
        "fulltime": "Full-time",
        "parttime": "Part-time",
        "contract": "Contract",
        "contractor": "Contract",
        "intern": "Intern",
        "internship": "Intern",
        "temporary": "Temporary",
        "permanent": "Permanent",
    }
    return known.get(key, text)


def normalize_remote_status(explicit: Any, location: Any) -> str:
    explicit_text = non_empty_str(explicit)
    if explicit_text:
        normalized = explicit_text.lower().replace("_", "-")
        if normalized in {"remote", "fully-remote", "work-from-home"}:
            return "remote"
        if normalized in {"hybrid", "flexible"}:
            return "hybrid"
        if normalized in {"onsite", "on-site", "office", "in-office"}:
            return "onsite"

    location_text = non_empty_str(location)
    if location_text:
        lowered = location_text.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        if "on-site" in lowered or "onsite" in lowered or "in office" in lowered:
            return "onsite"

    return "unknown"


def format_salary(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return non_empty_str(value)
    if not isinstance(value, dict):
        return None

    minimum = value.get("min", value.get("minimum"))
    maximum = value.get("max", value.get("maximum"))
    currency = non_empty_str(value.get("currency"))
    interval = non_empty_str(value.get("interval") or value.get("period") or value.get("frequency"))

    if minimum is None and maximum is None:
        return None

    amount = ""
    if minimum is not None and maximum is not None:
        amount = f"{minimum}-{maximum}"
    elif minimum is not None:
        amount = f"from {minimum}"
    else:
        amount = f"up to {maximum}"

    suffix = " ".join(part for part in (currency, interval) if part)
    return f"{amount} {suffix}".strip()


def epoch_ms_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            value = float(stripped)
        except ValueError:
            return stripped
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat()
    return None
