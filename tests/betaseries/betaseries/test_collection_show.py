"""Tests for CollectionShow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.show import Show


def test_for_show_returns_known_show() -> None:
    """Return the show for a show id present in the collection."""
    show = Show(id="38605", title="Example Show")
    collection = CollectionShow({"38605": show})

    assert collection.for_show("38605") is show


def test_for_show_returns_none_for_unknown_show() -> None:
    """Return None for a show id absent from the collection."""
    collection = CollectionShow({})

    assert collection.for_show("unknown") is None


async def test_fetch_episodes_calls_client_once_per_show() -> None:
    """Call client.fetch_show_episodes() once per show in the collection, with its id.

    Client.fetch_show_episodes() has no verified bulk support, unlike
    fetch_shows() - so this issues one request per show.
    """
    collection = CollectionShow(
        {
            "10": Show(id="10", title="Show A"),
            "20": Show(id="20", title="Show B"),
        }
    )

    def _episodes_for(show_id: str) -> str:
        return f"episodes-{show_id}"

    client = AsyncMock()
    client.fetch_show_episodes.side_effect = _episodes_for

    result = await collection.fetch_episodes(client)

    assert client.fetch_show_episodes.await_count == 2
    client.fetch_show_episodes.assert_any_await("10")
    client.fetch_show_episodes.assert_any_await("20")

    show_a = result.for_show("10")
    show_b = result.for_show("20")
    assert show_a is not None
    assert show_b is not None
    assert show_a.episodes == "episodes-10"
    assert show_b.episodes == "episodes-20"


async def test_fetch_episodes_does_not_mutate_original_collection() -> None:
    """Leave the original collection's shows untouched (Show is frozen)."""
    collection = CollectionShow({"10": Show(id="10", title="Show A")})
    client = AsyncMock()
    client.fetch_show_episodes.return_value = "episodes-10"

    await collection.fetch_episodes(client)

    show = collection.for_show("10")
    assert show is not None
    assert show.episodes is None


async def test_fetch_additional_information_calls_client_once_for_all_shows() -> None:
    """Call client.fetch_shows() once, with every show id in the collection (bulk endpoint)."""
    collection = CollectionShow(
        {
            "10": Show(id="10", title="Show A"),
            "20": Show(id="20", title="Show B"),
        }
    )
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    await collection.fetch_additional_information(client)

    client.fetch_shows.assert_awaited_once()
    (show_ids,), _kwargs = client.fetch_shows.await_args
    assert set(show_ids) == {"10", "20"}


async def test_fetch_additional_information_replaces_each_show_with_the_fetched_one() -> None:
    """Replace each show entirely with its freshly-fetched version.

    description/slug are refreshed too, not just additional_information - no
    reason to keep the older/lighter value once /shows/display's is available
    (see Show.fetch_additional_information()).
    """
    collection = CollectionShow(
        {
            "10": Show(id="10", title="Show A", description="Stale description A"),
            "20": Show(id="20", title="Show B"),
        }
    )
    fetched_a = Show(
        id="10",
        title="Show A",
        description="Fresh description A",
        additional_information="info-10",  # type: ignore[arg-type]
    )
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"10": fetched_a})

    result = await collection.fetch_additional_information(client)

    show_a = result.for_show("10")
    show_b = result.for_show("20")
    assert show_a is fetched_a
    assert show_a is not None
    assert show_a.description == "Fresh description A"
    assert show_a.additional_information == "info-10"
    # Show 20 wasn't in the client's response: it's kept as-is.
    assert show_b is not None
    assert show_b.additional_information is None
