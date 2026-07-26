"""Bundled BetaSeries API client.

Self-contained: it can be extracted as its own PyPI package as-is if it's ever needed outside this project.
"""

from __future__ import annotations

from .auth import Auth
from .client import Client
from .collection_episode import CollectionEpisode
from .collection_show import CollectionShow
from .device_code import DeviceCodeData
from .episode import Episode
from .exceptions import AuthError, AuthTimeoutError, Error
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .show import Show
from .show_additional_information import ShowAdditionalInformation
from .show_images import ShowImages

__all__ = [
    "Auth",
    "AuthError",
    "AuthTimeoutError",
    "Client",
    "CollectionEpisode",
    "CollectionShow",
    "DeviceCodeData",
    "Episode",
    "Error",
    "MemberData",
    "MemberIdentity",
    "MemberStats",
    "Show",
    "ShowAdditionalInformation",
    "ShowImages",
]
