"""Tests for Episode."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.show import Show


def _make_episode(show_id: str) -> Episode:
    """Build a minimal Episode for testing.

    Args:
        show_id (str): The episode's show id.

    Returns:
        Episode: A minimal episode with the given show id.

    """
    return Episode(
        id="1",
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


async def test_fetch_show_calls_client_with_its_show_id() -> None:
    """Call client.fetch_shows() with this episode's show id, alone in a list."""
    episode = _make_episode("10")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    await episode.fetch_show(client)

    client.fetch_shows.assert_awaited_once_with(["10"])


async def test_fetch_show_replaces_show_with_enriched_version() -> None:
    """Replace the episode's show with the enriched Show fetched from the client."""
    episode = _make_episode("10")
    enriched_show = Show(id="10", title="Enriched Show")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"10": enriched_show})

    result = await episode.fetch_show(client)

    assert result is not episode
    assert result.show is enriched_show


async def test_fetch_show_keeps_original_show_if_not_in_response() -> None:
    """Keep the episode's original show if the client's response doesn't include it."""
    episode = _make_episode("10")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    result = await episode.fetch_show(client)

    assert result.show.id == "10"
    assert result.show.title == "Example Show"


async def test_fetch_show_does_not_mutate_original_episode() -> None:
    """Leave the original Episode untouched (Episode is frozen)."""
    episode = _make_episode("10")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"10": Show(id="10", title="Enriched Show")})

    await episode.fetch_show(client)

    assert episode.show.title == "Example Show"
