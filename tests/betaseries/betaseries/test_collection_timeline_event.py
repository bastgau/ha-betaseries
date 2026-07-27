"""Tests for CollectionTimelineEvent."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.collection_timeline_event import CollectionTimelineEvent
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.episode_watched_event import EpisodeWatchedEvent
from custom_components.betaseries.betaseries.season_watched_event import SeasonWatchedEvent
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.timeline_event import TimelineEvent

EVENT_DATE = datetime(2026, 7, 26, 5, 20, 30)  # noqa: DTZ001 (API doesn't return a timezone)


def _make_episode_event(event_id: str, episode_id: str) -> EpisodeWatchedEvent:
    """Build a minimal EpisodeWatchedEvent for testing.

    Args:
        event_id (str): The event's id.
        episode_id (str): The watched episode's id.

    Returns:
        EpisodeWatchedEvent: A minimal event with the given ids.

    """
    return EpisodeWatchedEvent(id=event_id, date=EVENT_DATE, episode_id=episode_id)


def _make_season_event(event_id: str, show_id: str, season: int = 1) -> SeasonWatchedEvent:
    """Build a minimal SeasonWatchedEvent for testing.

    Args:
        event_id (str): The event's id.
        show_id (str): The show's id.
        season (int): The season number (default 1).

    Returns:
        SeasonWatchedEvent: A minimal event with the given ids.

    """
    return SeasonWatchedEvent(id=event_id, date=EVENT_DATE, show_id=show_id, season=season)


def _make_full_episode(episode_id: str, show: Show) -> Episode:
    """Build a minimal Episode for testing, with a given show attached.

    Args:
        episode_id (str): The episode's id.
        show (Show): The show to attach.

    Returns:
        Episode: A minimal episode with the given id and show.

    """
    return Episode(
        id=episode_id,
        season=1,
        number=1,
        code="S01E01",
        title="Pilot",
        description="",
        air_date=EVENT_DATE.date(),
        seen=True,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1",
        show=show,
    )


def test_iterates_over_wrapped_events() -> None:
    """Iterate over the wrapped events, in order."""
    events = (_make_episode_event("1", "10"), _make_season_event("2", "20"))
    collection = CollectionTimelineEvent(events)

    assert list(collection) == list(events)


def test_len_returns_event_count() -> None:
    """Return the number of wrapped events."""
    events = (_make_episode_event("1", "10"), _make_season_event("2", "20"))
    collection = CollectionTimelineEvent(events)

    assert len(collection) == 2


async def test_fetch_shows_calls_client_with_episode_and_show_ids() -> None:
    """Call fetch_episodes_by_id for EpisodeWatchedEvent, fetch_shows for SeasonWatchedEvent."""
    events = (_make_episode_event("1", "111"), _make_season_event("2", "99"))
    collection = CollectionTimelineEvent(events)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode(())
    client.fetch_shows.return_value = CollectionShow({})

    await collection.fetch_shows(client)

    client.fetch_episodes_by_id.assert_awaited_once_with({"111"})
    client.fetch_shows.assert_awaited_once_with({"99"})


async def test_fetch_shows_populates_episode_watched_event_show_and_episode() -> None:
    """Populate both `show` and `episode` on EpisodeWatchedEvent from a single fetch."""
    events = (_make_episode_event("1", "111"),)
    collection = CollectionTimelineEvent(events)
    show = Show(id="42", title="Silo")
    episode = _make_full_episode("111", show)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode((episode,))
    client.fetch_shows.return_value = CollectionShow({})

    result = await collection.fetch_shows(client)

    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.show is show
    assert enriched.episode is episode


async def test_fetch_shows_populates_season_watched_event_show() -> None:
    """Populate `show` on SeasonWatchedEvent by fetching its show_id directly."""
    events = (_make_season_event("1", "99"),)
    collection = CollectionTimelineEvent(events)
    show = Show(id="99", title="Below Deck Mediterranean")
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode(())
    client.fetch_shows.return_value = CollectionShow({"99": show})

    result = await collection.fetch_shows(client)

    enriched = next(iter(result))
    assert isinstance(enriched, SeasonWatchedEvent)
    assert enriched.show is show


async def test_fetch_shows_skips_episode_already_carrying_episode() -> None:
    """Reuse the already-fetched `episode.show` without calling fetch_episodes_by_id."""
    show = Show(id="42", title="Silo")
    episode = _make_full_episode("111", show)
    event = EpisodeWatchedEvent(id="1", date=EVENT_DATE, episode_id="111", episode=episode)
    collection = CollectionTimelineEvent((event,))
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    result = await collection.fetch_shows(client)

    client.fetch_episodes_by_id.assert_not_awaited()
    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.show is show


async def test_fetch_shows_skips_events_already_carrying_show() -> None:
    """Leave events that already have a `show` untouched, with no request for them."""
    existing_show = Show(id="42", title="Silo")
    event = EpisodeWatchedEvent(id="1", date=EVENT_DATE, episode_id="111", show=existing_show)
    collection = CollectionTimelineEvent((event,))
    client = AsyncMock()

    result = await collection.fetch_shows(client)

    client.fetch_episodes_by_id.assert_not_awaited()
    client.fetch_shows.assert_not_awaited()
    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.show is existing_show


async def test_fetch_shows_leaves_other_event_types_unchanged() -> None:
    """Leave events of an unmodeled TimelineEvent subtype untouched."""
    event = TimelineEvent(id="1", date=EVENT_DATE)
    collection = CollectionTimelineEvent((event,))
    client = AsyncMock()

    result = await collection.fetch_shows(client)

    assert next(iter(result)) is event


async def test_fetch_shows_does_not_mutate_original_collection() -> None:
    """Leave the original collection's events untouched (frozen dataclasses)."""
    events = (_make_episode_event("1", "111"),)
    collection = CollectionTimelineEvent(events)
    show = Show(id="42", title="Silo")
    episode = _make_full_episode("111", show)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode((episode,))
    client.fetch_shows.return_value = CollectionShow({})

    await collection.fetch_shows(client)

    original = next(iter(collection))
    assert isinstance(original, EpisodeWatchedEvent)
    assert original.show is None


async def test_fetch_episodes_calls_client_with_episode_ids() -> None:
    """Call fetch_episodes_by_id with the episode ids of every EpisodeWatchedEvent."""
    events = (_make_episode_event("1", "111"), _make_season_event("2", "99"))
    collection = CollectionTimelineEvent(events)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode(())

    await collection.fetch_episodes(client)

    client.fetch_episodes_by_id.assert_awaited_once_with({"111"})


async def test_fetch_episodes_populates_episode_watched_event() -> None:
    """Populate `episode` on EpisodeWatchedEvent from the client's response."""
    events = (_make_episode_event("1", "111"),)
    collection = CollectionTimelineEvent(events)
    show = Show(id="42", title="Silo")
    episode = _make_full_episode("111", show)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode((episode,))

    result = await collection.fetch_episodes(client)

    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.episode is episode
    assert enriched.show is show


async def test_fetch_episodes_keeps_existing_show_over_the_fetched_episodes_show() -> None:
    """Prefer an event's existing `show` (from a prior fetch_shows()) over the episode's own.

    The freshly-fetched episode still carries its own `show` (the API
    returns it for free) - that duplicate must not override the event's
    existing show, so the two never disagree after this call.
    """
    existing_show = Show(id="42", title="Silo (existing)")
    event = EpisodeWatchedEvent(id="1", date=EVENT_DATE, episode_id="111", show=existing_show)
    collection = CollectionTimelineEvent((event,))
    fetched_show = Show(id="42", title="Silo (freshly fetched)")
    episode = _make_full_episode("111", fetched_show)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode((episode,))

    result = await collection.fetch_episodes(client)

    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.show is existing_show
    assert enriched.episode is not None
    assert enriched.episode.show is existing_show


async def test_fetch_episodes_skips_events_already_carrying_episode() -> None:
    """Leave events that already have an `episode` untouched, with no request for them."""
    show = Show(id="42", title="Silo")
    existing_episode = _make_full_episode("111", show)
    event = EpisodeWatchedEvent(id="1", date=EVENT_DATE, episode_id="111", episode=existing_episode)
    collection = CollectionTimelineEvent((event,))
    client = AsyncMock()

    result = await collection.fetch_episodes(client)

    client.fetch_episodes_by_id.assert_not_awaited()
    enriched = next(iter(result))
    assert isinstance(enriched, EpisodeWatchedEvent)
    assert enriched.episode is existing_episode


async def test_fetch_episodes_leaves_season_watched_event_unchanged() -> None:
    """Leave SeasonWatchedEvent untouched - it has no single episode_id to fetch."""
    event = _make_season_event("1", "99")
    collection = CollectionTimelineEvent((event,))
    client = AsyncMock()

    result = await collection.fetch_episodes(client)

    assert next(iter(result)) is event


async def test_fetch_episodes_does_not_mutate_original_collection() -> None:
    """Leave the original collection's events untouched (frozen dataclasses)."""
    events = (_make_episode_event("1", "111"),)
    collection = CollectionTimelineEvent(events)
    show = Show(id="42", title="Silo")
    episode = _make_full_episode("111", show)
    client = AsyncMock()
    client.fetch_episodes_by_id.return_value = CollectionEpisode((episode,))

    await collection.fetch_episodes(client)

    original = next(iter(collection))
    assert isinstance(original, EpisodeWatchedEvent)
    assert original.episode is None
