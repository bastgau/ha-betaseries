"""Tests for Show."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.show import Show


def test_resource_url_derived_from_slug() -> None:
    """Derive the show's page URL from its slug (verified pattern, see bruno/Shows/display.bru)."""
    show = Show(id="38605", title="Achtsam Morden", slug="achtsam-morden")

    assert show.resource_url == "https://www.betaseries.com/serie/achtsam-morden"


def test_resource_url_is_none_without_slug() -> None:
    """Return None when the slug is unknown (default None)."""
    show = Show(id="6947", title="Below Deck")

    assert show.resource_url is None


async def test_fetch_episodes_attaches_episodes_to_a_new_show() -> None:
    """Fetch episodes via client.fetch_show_episodes() and return a new Show with them attached."""
    show = Show(id="6947", title="Below Deck")
    client = AsyncMock()
    client.fetch_show_episodes.return_value = "sentinel-episodes"

    result = await show.fetch_episodes(client)

    client.fetch_show_episodes.assert_awaited_once_with("6947")
    assert result is not show
    assert result.id == "6947"
    assert result.title == "Below Deck"
    assert result.episodes == "sentinel-episodes"


async def test_fetch_episodes_does_not_mutate_original_show() -> None:
    """Leave the original Show untouched (Show is frozen)."""
    show = Show(id="6947", title="Below Deck")
    client = AsyncMock()
    client.fetch_show_episodes.return_value = "sentinel-episodes"

    await show.fetch_episodes(client)

    assert show.episodes is None


async def test_fetch_additional_information_returns_the_freshly_fetched_show() -> None:
    """Fetch this show via client.fetch_shows([id]) and return it, refreshing every field."""
    show = Show(id="38605", title="Achtsam Morden", description="Stale description")
    fetched = Show(
        id="38605",
        title="Achtsam Morden",
        description="Fresh description",
        slug="achtsam-morden",
        additional_information="sentinel-info",
    )
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({"38605": fetched})

    result = await show.fetch_additional_information(client)

    client.fetch_shows.assert_awaited_once_with(["38605"])
    assert result is fetched
    # description/slug are refreshed too, not just additional_information -
    # no reason to keep the older/lighter value once /shows/display's is available.
    assert result.description == "Fresh description"
    assert result.slug == "achtsam-morden"
    assert result.additional_information == "sentinel-info"


async def test_fetch_additional_information_keeps_original_if_unexpectedly_absent() -> None:
    """Keep the original Show as-is if the client's response omits it entirely."""
    show = Show(id="38605", title="Achtsam Morden")
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})

    result = await show.fetch_additional_information(client)

    assert result is show
