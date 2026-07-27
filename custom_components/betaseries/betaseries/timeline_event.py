"""Common fields shared by every timeline event, as returned by GET /timeline/member.

Not meant to be instantiated directly - use a subclass (see
episode_watched_event.py, season_watched_event.py). Only
EPISODE_WATCHED/SEASON_WATCHED events get a dedicated subclass for now (the
ones a future watch-history calendar would need, see
docs/watch-history-calendar-exploration.md). The other known event types
(SHOW_ADDED, SHOW_REMOVED, SHOW_ARCHIVED, SHOW_UNARCHIVED, BADGE_EARNED) are
dropped at parse time - TimelineEventType still lists them so a dedicated
subclass can be added later without rediscovering these values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class TimelineEvent:
    """Common fields shared by every timeline event.

    Attributes:
        id (str): BetaSeries event id, used as the since_id/last_id pagination cursor.
        date (datetime): When the event occurred (local time, no timezone info from the API).

    """

    id: str
    date: datetime
