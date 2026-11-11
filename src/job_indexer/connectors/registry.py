from __future__ import annotations

from ..http import HttpClient
from .ashby import AshbyConnector
from .bamboohr import BambooHRConnector
from .breezy import BreezyConnector
from .base import Connector
from .greenhouse import GreenhouseConnector
from .jazzhr import JazzHRConnector
from .lever import LeverConnector
from .niceboard import NiceboardConnector
from .personio import PersonioConnector
from .pinpoint import PinpointConnector
from .recruitee import RecruiteeConnector
from .rippling import RipplingConnector
from .smartrecruiters import SmartRecruitersConnector
from .teamtailor import TeamtailorConnector
from .workable import WorkableConnector
from .workday import WorkdayConnector


SUPPORTED_PLATFORMS = (
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
    "recruitee",
    "pinpoint",
    "personio",
    "teamtailor",
    "rippling",
    "workday",
    "breezy",
    "bamboohr",
    "jazzhr",
    "niceboard",
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
    if platform == "recruitee":
        return RecruiteeConnector(http)
    if platform == "pinpoint":
        return PinpointConnector(http)
    if platform == "personio":
        return PersonioConnector(http)
    if platform == "teamtailor":
        return TeamtailorConnector(http)
    if platform == "rippling":
        return RipplingConnector(http)
    if platform == "workday":
        return WorkdayConnector(http)
    if platform == "breezy":
        return BreezyConnector(http)
    if platform == "bamboohr":
        return BambooHRConnector(http)
    if platform == "jazzhr":
        return JazzHRConnector(http)
    if platform == "niceboard":
        return NiceboardConnector(http)
    raise ValueError(f"unsupported platform: {platform!r}")
