"""Bundled BetaSeries API client.

Self-contained: it can be extracted as its own PyPI package as-is if it's ever needed outside this project.
"""

from __future__ import annotations

from .auth import Auth
from .badge import Badge
from .client import Client
from .collection_badge import CollectionBadge
from .collection_episode import CollectionEpisode
from .collection_show import CollectionShow
from .collection_timeline_event import CollectionTimelineEvent
from .collection_watch_list_show import CollectionWatchListShow
from .device_code import DeviceCodeData
from .episode import Episode
from .episode_watched_event import EpisodeWatchedEvent
from .exceptions import AuthError, AuthTimeoutError, Error, NotWatchedError
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .season_watched_event import SeasonWatchedEvent
from .show import Show
from .show_additional_information import ShowAdditionalInformation
from .show_images import ShowImages
from .timeline_event import TimelineEvent
from .timeline_event_type import TimelineEventType
from .watch_list_show import WatchListShow

__all__ = [
    "Auth",
    "AuthError",
    "AuthTimeoutError",
    "Badge",
    "Client",
    "CollectionBadge",
    "CollectionEpisode",
    "CollectionShow",
    "CollectionTimelineEvent",
    "CollectionWatchListShow",
    "DeviceCodeData",
    "Episode",
    "EpisodeWatchedEvent",
    "Error",
    "MemberData",
    "MemberIdentity",
    "MemberStats",
    "NotWatchedError",
    "SeasonWatchedEvent",
    "Show",
    "ShowAdditionalInformation",
    "ShowImages",
    "TimelineEvent",
    "TimelineEventType",
    "WatchListShow",
]
