"""Tests for PlanningCoordinator.

Client error handling (AuthError/Error translation) is covered by the
shared, parametrized tests in test_coordinator_errors.py instead of here.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.planning_episode import PlanningEpisode
from custom_components.betaseries.const import CONF_PLANNING_SCAN_INTERVAL, DOMAIN
from custom_components.betaseries.coordinator import (
    PlanningCoordinator,
    _upcoming_months,  # pyright: ignore[reportPrivateUsage]
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

EPISODE = PlanningEpisode(
    id="1001",
    show_id="55",
    show_title="Example Show",
    season=3,
    episode=4,
    code="S03E04",
    title="The One With The Tests",
    description="A thrilling episode summary.",
    air_date=date(2026, 8, 1),
    seen=False,
    platforms=("Netflix",),
    resource_url="https://www.betaseries.com/episode/1001",
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
    """Aggregate episodes fetched across the current month and the months ahead."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_planning.return_value = (EPISODE,)

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == (EPISODE, EPISODE, EPISODE)
    assert mock_client.fetch_planning.await_count == 3


async def test_update_success_sorts_by_air_date(hass: HomeAssistant) -> None:
    """Sort the aggregated episodes by air_date, regardless of fetch order."""
    later_episode = EPISODE
    earlier_episode = PlanningEpisode(
        id="999",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=3,
        code="S03E03",
        title="An Earlier Episode",
        description="An earlier episode summary.",
        air_date=date(2026, 7, 20),
        seen=False,
        platforms=("Netflix",),
        resource_url="https://www.betaseries.com/episode/999",
    )
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_planning.side_effect = [(later_episode,), (earlier_episode,), ()]

    coordinator = PlanningCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.data == (earlier_episode, later_episode)
