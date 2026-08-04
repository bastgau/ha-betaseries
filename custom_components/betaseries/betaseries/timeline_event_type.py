"""Event types observed on GET /timeline/member.

Not documented as an enum in openapi.json (the `types` filter param is a
free-form string there) - this list is derived empirically from a real
100-event sample (see bruno/Timeline/member.bru). Other values may exist
that this sample didn't cover.
"""

from __future__ import annotations

from enum import StrEnum


class TimelineEventType(StrEnum):
    """Known values of a timeline event's "type" field."""

    EPISODE_WATCHED = "markas"
    SEASON_WATCHED = "season_watched"
    SHOW_ADDED = "add_serie"
    SHOW_REMOVED = "del_serie"
    SHOW_ARCHIVED = "archive"
    SHOW_UNARCHIVED = "unarchive"
    BADGE_EARNED = "badge"
