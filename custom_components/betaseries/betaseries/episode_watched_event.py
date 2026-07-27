"""A single episode marked as watched, as returned by GET /timeline/member."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .timeline_event import TimelineEvent
from .timeline_event_type import TimelineEventType

if TYPE_CHECKING:
    from .episode import Episode
    from .show import Show


@dataclass(frozen=True)
class EpisodeWatchedEvent(TimelineEvent):
    """A single episode marked as watched (TimelineEventType.EPISODE_WATCHED).

    Attributes:
        episode_id (str): BetaSeries id of the watched episode.
        event_type (TimelineEventType): Always TimelineEventType.EPISODE_WATCHED.
        show (Show | None): The episode's show, if fetched via CollectionTimelineEvent.fetch_shows() (None otherwise).
        episode (Episode | None): The full episode, if fetched via CollectionTimelineEvent.fetch_episodes() (None otherwise).

    """

    episode_id: str
    event_type: TimelineEventType = TimelineEventType.EPISODE_WATCHED
    show: Show | None = None
    episode: Episode | None = None
