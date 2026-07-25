"""Bundled BetaSeries API client.

Kept as a self-contained sub-package rather than a PyPI dependency: this is
a custom/HACS integration, not a core one, so the "external requirement"
rule does not apply (see project docs). This sub-package has no dependency
on Home Assistant, so it can be extracted as its own PyPI package as-is if
this integration is ever proposed for core.
"""

from __future__ import annotations

from .auth import Auth
from .client import Client
from .device_code import DeviceCodeData
from .exceptions import AuthError, AuthTimeoutError, Error
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .planning_episode import PlanningEpisode

__all__ = [
    "Auth",
    "AuthError",
    "AuthTimeoutError",
    "Client",
    "DeviceCodeData",
    "Error",
    "MemberData",
    "MemberIdentity",
    "MemberStats",
    "PlanningEpisode",
]
