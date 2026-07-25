"""Tests for BetaSeries async_setup_entry / async_unload_entry."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator, PlanningCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret"}

MEMBER_DATA = MemberData(
    id="42",
    login="test_user",
    xp=1337,
    stats=MemberStats(
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


async def test_setup_entry_creates_coordinator(hass: HomeAssistant) -> None:
    """Set up the entry, populating runtime_data with a refreshed MemberCoordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert isinstance(entry.runtime_data.member, MemberCoordinator)
    assert entry.runtime_data.member.data == MEMBER_DATA
    assert isinstance(entry.runtime_data.planning, PlanningCoordinator)
    assert entry.runtime_data.planning.data == ()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Unload a previously set up entry successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
