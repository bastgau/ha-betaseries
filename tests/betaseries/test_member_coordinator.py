"""Tests for MemberCoordinator.

Client error handling (AuthError/Error translation) is covered by the
shared, parametrized tests in test_coordinator_errors.py instead of here.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import CONF_MEMBER_SCAN_INTERVAL, DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

MEMBER_DATA = MemberData(
    identity=MemberIdentity(id="42", login="test_user"),
    stats=MemberStats(
        xp=1337,
        episodes_to_watch=12,
        time_to_spend=540,
        progress=77.4699,
        shows_to_watch=3,
        movies_to_watch=2,
        shows_current=5,
        badges=8,
        shows=40,
        shows_finished=30,
        episodes=1200,
        time_on_tv=54000,
        movies=100,
        streak_days=15,
        member_since_days=3650,
        episodes_per_month=25.5,
        favorite_genre="Drama",
    ),
)


async def test_uses_default_scan_interval(hass: HomeAssistant) -> None:
    """Default to 15 minutes when no member_scan_interval option is set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)

    coordinator = MemberCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=15)


async def test_uses_configured_scan_interval(hass: HomeAssistant) -> None:
    """Use the member_scan_interval option when set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", options={CONF_MEMBER_SCAN_INTERVAL: 30})
    entry.add_to_hass(hass)

    coordinator = MemberCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=30)


async def test_update_success(hass: HomeAssistant) -> None:
    """Store the member data fetched from the client after a successful refresh."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == MEMBER_DATA
