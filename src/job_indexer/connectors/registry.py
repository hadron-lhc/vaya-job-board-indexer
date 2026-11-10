from __future__ import annotations

from ..http import HttpClient
from .base import Connector
from .greenhouse import GreenhouseConnector
from .lever import LeverConnector


SUPPORTED_PLATFORMS = ("greenhouse", "lever")


def build_connector(platform: str, http: HttpClient) -> Connector:
    if platform == "greenhouse":
        return GreenhouseConnector(http)
    if platform == "lever":
        return LeverConnector(http)
    raise ValueError(f"unsupported platform: {platform!r}")
