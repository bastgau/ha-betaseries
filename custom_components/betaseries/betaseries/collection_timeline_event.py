"""A collection of the member's timeline events, as returned by GET /timeline/member."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from .episode_watched_event import EpisodeWatchedEvent
from .season_watched_event import SeasonWatchedEvent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .client import Client
    from .timeline_event import TimelineEvent


class CollectionTimelineEvent:
    """Wrap the member's timeline events.

    Attributes:
        _events (tuple[TimelineEvent, ...]): The wrapped events.

    """

    def __init__(self, events: tuple[TimelineEvent, ...]) -> None:
        """Initialize the collection.

        Args:
            events (tuple[TimelineEvent, ...]): The events to wrap.

        """
        self._events = events

    def __iter__(self) -> Iterator[TimelineEvent]:
        """Iterate over the wrapped events.

        Returns:
            Iterator[TimelineEvent]: An iterator over the events.

        """
        return iter(self._events)

    def __len__(self) -> int:
        """Return the number of wrapped events.

        Returns:
            int: The number of events.

        """
        return len(self._events)

    async def fetch_shows(self, client: Client) -> CollectionTimelineEvent:
        """Fetch every show referenced by these events, and return them merged back in.

        EpisodeWatchedEvent.show is populated from its already-fetched
        `episode.show` when present (no request needed - see fetch_episodes),
        otherwise by fetching the episode itself (its show is only known
        through the episode, not directly - see
        docs/watch-history-calendar-exploration.md) - GET /episodes/display
        returns the full episode either way, so `episode` is populated too
        at no extra cost, letting a later fetch_episodes() skip re-fetching
        it. SeasonWatchedEvent.show is populated by fetching its show_id
        directly (no episode involved). Any event that already has a `show`
        is left untouched. Both remaining lookups use a single bulk request
        each (fetch_episodes_by_id/fetch_shows already support multiple
        ids). Any other event type is left unchanged.

        Args:
            client (Client): The BetaSeries API client to fetch shows with.

        Returns:
            CollectionTimelineEvent: A new collection with each supported event's show (and, for EpisodeWatchedEvent, episode) populated.

        """
        episode_ids = {
            event.episode_id
            for event in self._events
            if isinstance(event, EpisodeWatchedEvent) and event.show is None and event.episode is None
        }
        season_show_ids = {
            event.show_id for event in self._events if isinstance(event, SeasonWatchedEvent) and event.show is None
        }

        episodes = await client.fetch_episodes_by_id(episode_ids) if episode_ids else None
        episodes_by_id = {episode.id: episode for episode in episodes} if episodes else {}

        shows = await client.fetch_shows(season_show_ids) if season_show_ids else None

        def _enrich(event: TimelineEvent) -> TimelineEvent:
            if isinstance(event, EpisodeWatchedEvent) and event.show is None:
                if event.episode:
                    return dataclasses.replace(event, show=event.episode.show)
                episode = episodes_by_id.get(event.episode_id)
                return dataclasses.replace(event, show=episode.show, episode=episode) if episode else event
            if isinstance(event, SeasonWatchedEvent) and event.show is None and shows is not None:
                show = shows.for_show(event.show_id)
                return dataclasses.replace(event, show=show) if show else event
            return event

        return CollectionTimelineEvent(tuple(_enrich(event) for event in self._events))

    async def fetch_episodes(self, client: Client) -> CollectionTimelineEvent:
        """Fetch the full episode referenced by each EpisodeWatchedEvent, merged back in.

        Only EpisodeWatchedEvent is supported - SeasonWatchedEvent has no
        single episode_id to fetch (see docs/watch-history-calendar-exploration.md
        for the still-undecided "expand a season into its episodes" case).
        Any event that already has an `episode` is left untouched. Any other
        event type is left unchanged. Uses a single bulk request
        (fetch_episodes_by_id already supports multiple ids).

        When an event already has a `show` (from a prior fetch_shows()) but
        no `episode` yet, the freshly-fetched episode still has its own
        `show` (the API returns it for free) - that duplicate is discarded
        in favor of the event's existing `show`, so the two never disagree
        after this call.

        Args:
            client (Client): The BetaSeries API client to fetch episodes with.

        Returns:
            CollectionTimelineEvent: A new collection with each EpisodeWatchedEvent's episode populated.

        """
        episode_ids = {
            event.episode_id
            for event in self._events
            if isinstance(event, EpisodeWatchedEvent) and event.episode is None
        }
        episodes = await client.fetch_episodes_by_id(episode_ids) if episode_ids else None
        episodes_by_id = {episode.id: episode for episode in episodes} if episodes else {}

        def _enrich(event: TimelineEvent) -> TimelineEvent:
            if isinstance(event, EpisodeWatchedEvent) and event.episode is None:
                episode = episodes_by_id.get(event.episode_id)
                if episode is None:
                    return event
                if event.show is not None:
                    episode = dataclasses.replace(episode, show=event.show)
                return dataclasses.replace(event, episode=episode, show=event.show or episode.show)
            return event

        return CollectionTimelineEvent(tuple(_enrich(event) for event in self._events))
