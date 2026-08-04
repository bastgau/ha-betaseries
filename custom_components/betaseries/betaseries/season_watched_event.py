"""A whole season marked as watched at once, as returned by GET /timeline/member."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .timeline_event import TimelineEvent
from .timeline_event_type import TimelineEventType

if TYPE_CHECKING:
    from .show import Show


@dataclass(frozen=True)
class SeasonWatchedEvent(TimelineEvent):
    """A whole season marked as watched at once (TimelineEventType.SEASON_WATCHED).

    Unlike EpisodeWatchedEvent, the API doesn't list the individual episodes
    covered by this event - only the show/season it applies to (see
    docs/watch-history-calendar-exploration.md for how this event type
    consolidates/replaces individual EpisodeWatchedEvents once every episode
    of a season has been watched).

    Attributes:
        show_id (str): BetaSeries id of the show.
        season (int): Season number marked as watched.
        event_type (TimelineEventType): Always TimelineEventType.SEASON_WATCHED.
        show (Show | None): The show, if fetched via CollectionTimelineEvent.fetch_shows() (None otherwise).

    """

    show_id: str
    season: int
    event_type: TimelineEventType = TimelineEventType.SEASON_WATCHED
    show: Show | None = None
