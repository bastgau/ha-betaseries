"""Tests for CollectionEpisode."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.show import Show


def _make_episode(episode_id: str, show_id: str) -> Episode:
    """Build a minimal Episode for testing.

    Args:
        episode_id (str): The episode's id.
        show_id (str): The episode's show id.

    Returns:
        Episode: A minimal episode with the given ids.

    """
    return Episode(
        id=episode_id,
        season=1,
        number=1,
        code="S01E01",
        title="Pilot",
        description="A pilot episode.",
        air_date=date(2026, 8, 1),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1",
        show=Show(id=show_id, title="Example Show"),
    )


def test_iterates_over_wrapped_episodes() -> None:
    """Iterate over the wrapped episodes, in order."""
    episodes = (_make_episode("1", "10"), _make_episode("2", "20"))
    collection = CollectionEpisode(episodes)

    assert list(collection) == list(episodes)


def test_len_returns_episode_count() -> None:
    """Return the number of wrapped episodes."""
    episodes = (_make_episode("1", "10"), _make_episode("2", "20"))
    collection = CollectionEpisode(episodes)

    assert len(collection) == 2


def test_show_ids_deduplicates_across_episodes() -> None:
    """Return the unique show ids referenced by the wrapped episodes."""
    episodes = (_make_episode("1", "10"), _make_episode("2", "10"), _make_episode("3", "20"))
    collection = CollectionEpisode(episodes)

    assert collection.show_ids == frozenset({"10", "20"})


def test_show_ids_empty_for_no_episodes() -> None:
    """Return an empty frozenset when there are no episodes."""
    collection = CollectionEpisode(())

    assert collection.show_ids == frozenset()


async def test_fetch_shows_calls_client_with_show_ids() -> None:
    """Call client.fetch_shows() with this collection's unique show ids."""
    episodes = (_make_episode("1", "10"), _make_episode("2", "10"), _make_episode("3", "20"))
    collection = CollectionEpisode(episodes)
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    await collection.fetch_shows(client)

    client.fetch_shows.assert_awaited_once_with(collection.show_ids)


async def test_fetch_shows_merges_enriched_show_back_into_each_episode() -> None:
    """Replace each episode's show with the enriched Show fetched from the client."""
    episodes = (_make_episode("1", "10"), _make_episode("2", "20"))
    collection = CollectionEpisode(episodes)
    enriched_show_10 = Show(id="10", title="Enriched Show 10")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"10": enriched_show_10})

    result = await collection.fetch_shows(client)

    assert isinstance(result, CollectionEpisode)
    merged = {episode.id: episode for episode in result}
    assert merged["1"].show is enriched_show_10
    # Show 20 wasn't in the client's response: the episode keeps its original show.
    assert merged["2"].show.id == "20"
    assert merged["2"].show.title == "Example Show"


async def test_fetch_shows_does_not_mutate_original_collection() -> None:
    """Leave the original collection's episodes untouched (Episode is frozen)."""
    episodes = (_make_episode("1", "10"),)
    collection = CollectionEpisode(episodes)
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"10": Show(id="10", title="Enriched")})

    await collection.fetch_shows(client)

    assert next(iter(collection)).show.title == "Example Show"
