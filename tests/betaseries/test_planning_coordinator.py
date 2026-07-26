"""Tests for PlanningCoordinator.

Client error handling (AuthError/Error translation) is covered by the
shared, parametrized tests in test_coordinator_errors.py instead of here.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.const import (
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    DOMAIN,
    PLANNING_STORE_KEY_PREFIX,
)
from custom_components.betaseries.coordinator import (
    PlanningCoordinator,
    _past_months,  # pyright: ignore[reportPrivateUsage]
    _upcoming_months,  # pyright: ignore[reportPrivateUsage]
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    # Default: 2 months behind + current + 2 months ahead = 5 fetches.
    assert tuple(coordinator.data) == (EPISODE, EPISODE, EPISODE, EPISODE, EPISODE)
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
    mock_client = AsyncMock()
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
    mock_client = AsyncMock()
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode((later_episode,)),
        CollectionEpisode((earlier_episode,)),
    ]

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert tuple(coordinator.data) == (earlier_episode, later_episode)


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
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    assert mock_client.fetch_planning.await_count == 2  # 1 past month + current month

    mock_client.fetch_planning.reset_mock()
    await coordinator.async_refresh()

    # The past month is served from the store: only the current month is re-fetched.
    assert mock_client.fetch_planning.await_count == 1
    assert tuple(coordinator.data) == (EPISODE, EPISODE)


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
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    first_coordinator = PlanningCoordinator(hass, entry, mock_client)
    await first_coordinator.async_refresh()

    mock_client.fetch_planning.reset_mock()
    second_coordinator = PlanningCoordinator(hass, entry, mock_client)
    await second_coordinator.async_refresh()

    assert mock_client.fetch_planning.await_count == 1  # only the current month
    assert tuple(second_coordinator.data) == (EPISODE, EPISODE)


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
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()  # caches 2026-07

    stored = await coordinator.store.async_load()
    assert stored is not None
    assert set(stored) == {"2026-07"}

    # A whole year later: months_behind=1 now means "2027-07", so "2026-07" must
    # be pruned even though no month is missing from the cache (2027-08 is the
    # only "past" month requested, and it will be freshly fetched here too).
    freezer.move_to("2027-08-15")
    mock_client.fetch_planning.reset_mock()
    await coordinator.async_refresh()

    stored = await coordinator.store.async_load()
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
    Without _PastMonthsStore's discard-on-migrate, an existing cache from
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
        "version": 1,
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
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = CollectionEpisode((EPISODE,))

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    # The incompatible cache is discarded, so both the past and current month
    # are freshly fetched instead of the past month being served (and crashing).
    assert mock_client.fetch_planning.await_count == 2
    assert tuple(coordinator.data) == (EPISODE, EPISODE)
