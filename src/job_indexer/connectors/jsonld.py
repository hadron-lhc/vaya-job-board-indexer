from __future__ import annotations

import html
import json
import re
from typing import Any

from ..utils import format_salary, non_empty_str


JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def extract_jsonld_objects(text: str) -> list[Any]:
    objects: list[Any] = []
    for match in JSONLD_SCRIPT_RE.finditer(text):
        raw = html.unescape(match.group(1).strip())
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        objects.extend(_flatten(value))
    return objects


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, list):
        flattened: list[Any] = []
        for item in value:
            flattened.extend(_flatten(item))
        return flattened
    if isinstance(value, dict):
        flattened = [value]
        graph = value.get("@graph")
        if isinstance(graph, (list, dict)):
            flattened.extend(_flatten(graph))
        return flattened
    return []


def find_job_posting(text: str) -> dict[str, Any] | None:
    for item in extract_jsonld_objects(text):
        if not isinstance(item, dict):
            continue
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(value).lower() == "jobposting" for value in types if value is not None):
            return item
    return None


def job_posting_title(posting: dict[str, Any]) -> str | None:
    return non_empty_str(posting.get("title"))


def job_posting_description(posting: dict[str, Any]) -> str | None:
    return non_empty_str(posting.get("description"))


def job_posting_posted_at(posting: dict[str, Any]) -> str | None:
    return non_empty_str(posting.get("datePosted"))


def job_posting_company(posting: dict[str, Any]) -> str | None:
    organization = posting.get("hiringOrganization")
    if isinstance(organization, dict):
        return non_empty_str(organization.get("name"))
    return non_empty_str(organization)


def job_posting_employment_type(posting: dict[str, Any]) -> str | None:
    value = posting.get("employmentType")
    if isinstance(value, list):
        value = value[0] if value else None
    return non_empty_str(value)


def job_posting_location(posting: dict[str, Any]) -> str | None:
    value = posting.get("jobLocation")
    locations = value if isinstance(value, list) else [value]
    labels: list[str] = []
    for location in locations:
        label = _location_label(location)
        if label and label not in labels:
            labels.append(label)
    if labels:
        return "; ".join(labels)
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return "Remote"
    return None


def _location_label(value: Any) -> str | None:
    if not isinstance(value, dict):
        return non_empty_str(value)
    address = value.get("address")
    if isinstance(address, str):
        return non_empty_str(address)
    if not isinstance(address, dict):
        return non_empty_str(value.get("name"))
    parts = [
        non_empty_str(address.get("addressLocality")),
        non_empty_str(address.get("addressRegion")),
        non_empty_str(address.get("addressCountry")),
    ]
    text = ", ".join(part for part in parts if part)
    return text or non_empty_str(value.get("name"))


def job_posting_remote_status(posting: dict[str, Any], location: str | None) -> str | None:
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return "remote"
    return None


def job_posting_salary(posting: dict[str, Any]) -> str | None:
    value = posting.get("baseSalary")
    if value is None:
        return None
    if isinstance(value, str):
        return non_empty_str(value)
    if not isinstance(value, dict):
        return None
    currency = non_empty_str(value.get("currency"))
    amount = value.get("value")
    if isinstance(amount, dict):
        salary = format_salary(
            {
                "min": amount.get("minValue", amount.get("value")),
                "max": amount.get("maxValue"),
                "currency": currency,
                "interval": amount.get("unitText"),
            }
        )
        if salary is not None:
            return salary
        if amount.get("value") is not None:
            return f"{amount['value']} {currency or ''}".strip()
        return None
    return format_salary({"min": amount, "currency": currency})
