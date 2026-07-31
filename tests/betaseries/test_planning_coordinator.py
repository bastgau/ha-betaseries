"""Tests for PlanningCoordinator.

Client error handling (AuthError/Error translation) is covered by the
shared, parametrized tests in test_coordinator_errors.py instead of here.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.exceptions import Error
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.show_additional_information import ShowAdditionalInformation
from custom_components.betaseries.betaseries.show_images import ShowImages
from custom_components.betaseries.const import (
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    DOMAIN,
    PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX,
    PLANNING_SHOW_IMAGES_STORE_VERSION,
    PLANNING_STORE_KEY_PREFIX,
    PLANNING_STORE_VERSION,
)
from custom_components.betaseries.coordinator import (
    PlanningCoordinator,
    _past_months,  # pyright: ignore[reportPrivateUsage]
    _upcoming_months,  # pyright: ignore[reportPrivateUsage]
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import client_mock

if TYPE_CHECKING:
    from typing import Any

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

EPISODE = Episode(
    id="1001",
    season=3,
    number=4,
    code="S03E04",
    title="The One With The Tests",
    description="A thrilling episode summary.",
    air_date=date(2026, 8, 1),
    seen=False,
    platforms=("Netflix",),
    resource_url="https://www.betaseries.com/episode/1001",
    show=Show(id="55", title="Example Show", description="A show about tests.", slug="example-show"),
)

# The same episode as the coordinator hands it back once it has been through
# the past-months cache, which deliberately forgets the watch status (see
# _episode_to_dict). Past months go through it even on the refresh that
# fetches them, so this is what every past month yields, never EPISODE itself.
CACHED_EPISODE = dataclasses.replace(EPISODE, seen=None)


@pytest.mark.parametrize(
    ("today", "months_ahead", "expected"),
    [
        (date(2026, 8, 15), 0, ["2026-08"]),
        (date(2026, 8, 15), 2, ["2026-08", "2026-09", "2026-10"]),
        (date(2026, 11, 15), 2, ["2026-11", "2026-12", "2027-01"]),
        (date(2026, 12, 15), 1, ["2026-12", "2027-01"]),
    ],
)
def test_upcoming_months(today: date, months_ahead: int, expected: list[str]) -> None:
    """Build the month list, rolling over the year boundary correctly.

    Args:
        today (date): Reference date.
        months_ahead (int): Number of additional months requested.
        expected (list[str]): Expected "YYYY-MM" list.

    """
    assert _upcoming_months(today, months_ahead) == expected


@pytest.mark.parametrize(
    ("today", "months_behind", "expected"),
    [
        (date(2026, 8, 15), 0, []),
        (date(2026, 8, 15), 2, ["2026-06", "2026-07"]),
        (date(2027, 1, 15), 2, ["2026-11", "2026-12"]),
        (date(2026, 1, 15), 1, ["2025-12"]),
    ],
)
def test_past_months(today: date, months_behind: int, expected: list[str]) -> None:
    """Build the past month list, rolling over the year boundary correctly.

    Args:
        today (date): Reference date.
        months_behind (int): Number of past months requested.
        expected (list[str]): Expected "YYYY-MM" list.

    """
    assert _past_months(today, months_behind) == expected


async def test_uses_default_scan_interval(hass: HomeAssistant) -> None:
    """Default to 60 minutes when no planning_scan_interval option is set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)

    coordinator = PlanningCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=60)


async def test_uses_configured_scan_interval(hass: HomeAssistant) -> None:
    """Use the planning_scan_interval option when set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", options={CONF_PLANNING_SCAN_INTERVAL: 120})
    entry.add_to_hass(hass)

    coordinator = PlanningCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=120)


async def test_update_success_aggregates_all_months(hass: HomeAssistant) -> None:
    """Aggregate episodes fetched across past, current and future months."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    # Default: 2 months behind + current + 2 months ahead = 5 fetches.
    assert tuple(coordinator.data.episodes) == (CACHED_EPISODE, CACHED_EPISODE, EPISODE, EPISODE, EPISODE)
    assert mock_client.fetch_planning.await_count == 5


async def test_update_success_with_float_months_options(hass: HomeAssistant) -> None:
    """Accept months_ahead/months_behind stored as float, as NumberSelector produces.

    Regression test: config_flow.py's NumberSelector always coerces submitted
    values to float (see homeassistant.helpers.selector.NumberSelector.__call__),
    so options saved through the real options flow are floats, not ints. range()
    requires an int, so using the raw option value directly used to raise
    "'float' object cannot be interpreted as an integer" during setup.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1.0, CONF_PLANNING_MONTHS_AHEAD: 1.0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert mock_client.fetch_planning.await_count == 3  # 1 past + current + 1 ahead


async def test_update_success_sorts_by_air_date(hass: HomeAssistant) -> None:
    """Sort the aggregated episodes by air_date, regardless of fetch order."""
    later_episode = EPISODE
    earlier_episode = Episode(
        id="999",
        season=3,
        number=3,
        code="S03E03",
        title="An Earlier Episode",
        description="An earlier episode summary.",
        air_date=date(2026, 7, 20),
        seen=False,
        platforms=("Netflix",),
        resource_url="https://www.betaseries.com/episode/999",
        show=Show(id="55", title="Example Show"),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 1},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode((later_episode,)),
        CollectionEpisode((earlier_episode,)),
    ]

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert tuple(coordinator.data.episodes) == (earlier_episode, later_episode)


async def test_cached_episodes_come_back_with_an_unknown_watch_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """Never carry a watch status on a past month, fetched or cached.

    A cached month is never refetched, so a watch status persisted with it
    would still claim "unwatched" long after the member watched the episode.
    None says "not known", which is the truth and which `is False` filters
    reject - unlike a plain falsy test.

    A past month goes through the cache even on the refresh that fetches it
    (it is written, then read back), so this holds from the very first one:
    "was it seen" is simply not a question a past month answers, and there is
    no refresh where it briefly does.
    """
    freezer.move_to("2026-08-15")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    watched_last_month = Episode(
        id="1001",
        season=3,
        number=4,
        code="S03E04",
        title="Aired Last Month",
        description="",
        air_date=date(2026, 7, 15),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1001",
        show=Show(id="55", title="Example Show", description=None, slug="example-show"),
    )
    mock_client = client_mock()
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode((watched_last_month,)),  # 2026-07, cached from here on
        CollectionEpisode(()),  # 2026-08
    ]

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    # Written to the cache then read back, so already unknown on this refresh.
    assert next(iter(coordinator.data.episodes)).seen is None

    mock_client.fetch_planning.side_effect = [CollectionEpisode(())]  # only 2026-08 is refetched
    await coordinator.async_refresh()

    cached_episode = next(iter(coordinator.data.episodes))
    assert cached_episode.id == "1001"
    assert cached_episode.seen is None
    # Everything a past month *can* legitimately still assert survives.
    assert cached_episode.air_date == date(2026, 7, 15)
    assert cached_episode.title == "Aired Last Month"
    assert cached_episode.show.slug == "example-show"
    # And the watch status is gone from disk too, not merely ignored on read.
    stored = hass_storage[f"{PLANNING_STORE_KEY_PREFIX}_{entry.entry_id}"]["data"]
    assert "seen" not in stored["2026-07"][0]


async def test_past_months_are_cached_and_not_refetched(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Fetch past months once, then reuse the stored copy on subsequent refreshes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    assert mock_client.fetch_planning.await_count == 2  # 1 past month + current month

    mock_client.fetch_planning.reset_mock()
    await coordinator.async_refresh()

    # The past month is served from the store: only the current month is re-fetched.
    assert mock_client.fetch_planning.await_count == 1
    assert tuple(coordinator.data.episodes) == (CACHED_EPISODE, EPISODE)


async def test_past_months_persist_across_coordinator_instances(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Persist the cached past months so a new coordinator instance reuses them."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    first_coordinator = PlanningCoordinator(hass, entry, mock_client)
    await first_coordinator.async_refresh()

    mock_client.fetch_planning.reset_mock()
    second_coordinator = PlanningCoordinator(hass, entry, mock_client)
    await second_coordinator.async_refresh()

    assert mock_client.fetch_planning.await_count == 1  # only the current month
    assert tuple(second_coordinator.data.episodes) == (CACHED_EPISODE, EPISODE)


async def test_clean_planning_cache_refetches_cached_past_months(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Force a refetch of every month, including cached past ones, via the "Refresh planning" button."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="Test Account",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    assert mock_client.fetch_planning.await_count == 2  # 1 past month + current month

    mock_client.fetch_planning.reset_mock()
    with caplog.at_level(logging.DEBUG):
        await coordinator.async_clean_planning_cache()

    # Both the past month and the current month are re-fetched, bypassing the cache.
    assert mock_client.fetch_planning.await_count == 2
    assert tuple(coordinator.data.episodes) == (CACHED_EPISODE, EPISODE)
    assert "Clearing cached past months for Test Account" in caplog.text


async def test_cache_prunes_months_that_slid_out_of_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Drop a cached past month once it slides outside months_behind, even with nothing missing.

    Regression test: pruning used to only run when a month was missing from the
    cache, so a month that aged out of the window (without any new month needing
    a fetch) was never removed and the store grew unbounded over time.
    """
    freezer.move_to("2026-08-15")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()  # caches 2026-07

    stored = await coordinator.planning_store.async_load()
    assert stored is not None
    assert set(stored) == {"2026-07"}

    # A whole year later: months_behind=1 now means "2027-07", so "2026-07" must
    # be pruned even though no month is missing from the cache (2027-08 is the
    # only "past" month requested, and it will be freshly fetched here too).
    freezer.move_to("2027-08-15")
    mock_client.fetch_planning.reset_mock()
    await coordinator.async_refresh()

    stored = await coordinator.planning_store.async_load()
    assert stored is not None
    assert set(stored) == {"2027-07"}


async def test_incompatible_cache_version_is_discarded_not_crashed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """Discard a cache from an older, incompatible store version instead of crashing.

    Regression test: PLANNING_STORE_VERSION was bumped after Episode's cached
    dict shape changed ("episode" -> "number" - see coordinator._episode_to_dict).
    Without _CacheStore's discard-on-migrate, an existing cache from
    before that rename made _episode_from_dict raise KeyError: 'number',
    permanently failing PlanningCoordinator's setup for any pre-existing user.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        freezer (FrozenDateTimeFactory): Time-freezing fixture, for a stable "today".
        hass_storage (dict[str, Any]): The in-memory Store backing, pre-seeded with old data.

    """
    freezer.move_to("2026-08-15")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    store_key = f"{PLANNING_STORE_KEY_PREFIX}_{entry.entry_id}"
    hass_storage[store_key] = {
        # Any version older than the current one: _CacheStore discards it.
        "version": PLANNING_STORE_VERSION - 1,
        "minor_version": 1,
        "key": store_key,
        "data": {
            "2026-07": [
                {
                    "id": "1001",
                    "season": 3,
                    "episode": 4,  # old field name, before the "number" rename
                    "code": "S03E04",
                    "title": "Old Cache Shape",
                    "description": "",
                    "air_date": "2026-07-15",
                    "seen": False,
                    "platforms": [],
                    "resource_url": "https://www.betaseries.com/episode/1001",
                    "show_id": "55",
                    "show_title": "Example Show",
                }
            ]
        },
    }
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    # The incompatible cache is discarded, so both the past and current month
    # are freshly fetched instead of the past month being served (and crashing).
    assert mock_client.fetch_planning.await_count == 2
    assert tuple(coordinator.data.episodes) == (CACHED_EPISODE, EPISODE)


def _show_with_poster(show_id: str, poster: str | None, rating: float = 0.0) -> Show:
    """Build a Show carrying the additional information that holds its poster.

    Args:
        show_id (str): BetaSeries show id.
        poster (str | None): Poster URL, or None for a show that has no poster.
        rating (float): Mean member rating, cached alongside the poster.

    Returns:
        Show: The show, with additional_information populated.

    """
    return Show(
        id=show_id,
        title="Example Show",
        additional_information=ShowAdditionalInformation(
            original_title="Example Show",
            imdb_id=None,
            themoviedb_id=None,
            genres=(),
            showrunners=(),
            aliases=(),
            seasons=1,
            followers=0,
            network="Netflix",
            country=None,
            original_language=None,
            length=30,
            rating="",
            notes_mean=rating,
            notes_total=0,
            next_trailer=None,
            resource_url="https://www.betaseries.com/serie/example-show",
            images=ShowImages(show=None, banner=None, box=None, poster=poster, clearlogo=None),
        ),
    )


async def test_show_images_are_fetched_in_a_single_bulk_call(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Resolve every show of the window's poster with one /shows/display call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow(
        {"55": _show_with_poster("55", "https://pictures.betaseries.com/poster.jpg")}
    )

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.data.images == {"55": {"poster": "https://pictures.betaseries.com/poster.jpg"}}
    assert mock_client.fetch_shows.await_count == 1
    assert mock_client.fetch_shows.await_args.args[0] == ["55"]


async def test_show_images_are_cached_and_not_refetched(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Fetch a show's poster once, then reuse the stored copy on later refreshes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow(
        {"55": _show_with_poster("55", "https://pictures.betaseries.com/poster.jpg")}
    )

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert mock_client.fetch_shows.await_count == 1
    assert coordinator.data.images == {"55": {"poster": "https://pictures.betaseries.com/poster.jpg"}}


async def test_shows_without_any_image_are_cached_too(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Remember shows that have no poster, so they are not refetched every time.

    They are kept out of `posters` (there is nothing to display) but stay in
    the store, otherwise they would count as "missing" on every refresh.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow({"55": _show_with_poster("55", None)})

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert coordinator.data.images == {"55": {}}
    assert mock_client.fetch_shows.await_count == 1


async def test_show_images_of_shows_leaving_the_window_are_purged(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Drop cached posters of shows that are no longer in the planning window."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    hass_storage[f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{entry.entry_id}"] = {
        "version": PLANNING_SHOW_IMAGES_STORE_VERSION,
        "data": {"999": {"images": {"poster": "https://pictures.betaseries.com/gone.jpg"}, "rating": 4.2}},
    }
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow(
        {"55": _show_with_poster("55", "https://pictures.betaseries.com/poster.jpg")}
    )

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.data.images == {"55": {"poster": "https://pictures.betaseries.com/poster.jpg"}}
    stored = hass_storage[f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{entry.entry_id}"]["data"]
    assert "999" not in stored


async def test_show_ratings_ride_along_with_the_images(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Expose and cache each show's rating, taken from the poster call's own payload.

    GET /shows/display already carries `notes.mean`, so the rating the
    previous-episode sensor breaks its ties on costs no extra request - and
    is served from the same cache on the next refresh.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow(
        {"55": _show_with_poster("55", "https://pictures.betaseries.com/poster.jpg", rating=4.25)}
    )

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert coordinator.data.ratings == {"55": 4.25}
    # Served from the cache the second time round, like the images.
    assert mock_client.fetch_shows.await_count == 1
    stored = hass_storage[f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{entry.entry_id}"]["data"]
    assert stored["55"]["rating"] == 4.25


async def test_show_cache_entries_without_a_rating_are_refetched(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Refetch cached shows written before the cache also held the rating.

    The store version is deliberately not bumped for that shape change, so
    entries lacking the "images" key are treated as absent and refetched -
    the cache repairs itself instead of serving a shape nothing writes any
    more, or crashing on a missing key.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    hass_storage[f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{entry.entry_id}"] = {
        "version": PLANNING_SHOW_IMAGES_STORE_VERSION,
        # Old shape: the image mapping sat directly under the show id.
        "data": {"55": {"poster": "https://pictures.betaseries.com/stale.jpg"}},
    }
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.return_value = CollectionShow(
        {"55": _show_with_poster("55", "https://pictures.betaseries.com/fresh.jpg")}
    )

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert mock_client.fetch_shows.await_count == 1
    assert coordinator.data.images == {"55": {"poster": "https://pictures.betaseries.com/fresh.jpg"}}
    stored = hass_storage[f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{entry.entry_id}"]["data"]
    assert stored["55"]["images"] == {"poster": "https://pictures.betaseries.com/fresh.jpg"}


async def test_show_images_failure_does_not_fail_the_refresh(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Keep the planning usable when only the poster call fails.

    A poster is decoration: failing the whole update over it would take the
    calendar and both episode sensors down with it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))
    mock_client.fetch_shows.side_effect = Error("shows endpoint is down")

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert tuple(coordinator.data.episodes) == (EPISODE,)
    assert coordinator.data.images == {}


async def test_cache_newer_than_supported_is_discarded_not_fatal(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Drop a cache written by a newer integration version instead of failing setup.

    Store raises UnsupportedStorageVersionError - before _async_migrate_func
    ever runs - when the file's major version is higher than this class
    supports, which happens on a downgrade. These files only hold rebuildable
    cache, so _CacheStore discards them and logs why.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_PLANNING_MONTHS_BEHIND: 1, CONF_PLANNING_MONTHS_AHEAD: 0},
    )
    entry.add_to_hass(hass)
    store_key = f"{PLANNING_STORE_KEY_PREFIX}_{entry.entry_id}"
    hass_storage[store_key] = {
        "version": PLANNING_STORE_VERSION + 2,
        "minor_version": 1,
        "key": store_key,
        "data": {"2026-07": []},
    }
    mock_client = client_mock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    with caplog.at_level(logging.WARNING):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert "Discarding the" in caplog.text
    # Both months are refetched, as if nothing had ever been cached.
    assert mock_client.fetch_planning.await_count == 2
    assert tuple(coordinator.data.episodes) == (CACHED_EPISODE, EPISODE)
