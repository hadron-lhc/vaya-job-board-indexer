from __future__ import annotations

from ..http import HttpClient
from .ashby import AshbyConnector
from .base import Connector
from .greenhouse import GreenhouseConnector
from .lever import LeverConnector
from .smartrecruiters import SmartRecruitersConnector
from .workable import WorkableConnector


SUPPORTED_PLATFORMS = (
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
)


def build_connector(platform: str, http: HttpClient) -> Connector:
    if platform == "greenhouse":
        return GreenhouseConnector(http)
    if platform == "lever":
        return LeverConnector(http)
    if platform == "ashby":
        return AshbyConnector(http)
    if platform == "workable":
        return WorkableConnector(http)
    if platform == "smartrecruiters":
        return SmartRecruitersConnector(http)
    raise ValueError(f"unsupported platform: {platform!r}")
