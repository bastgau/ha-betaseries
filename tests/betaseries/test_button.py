"""Tests for BetaSeries button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import client_mock

from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}

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


async def _async_setup(hass: HomeAssistant, mock_client: AsyncMock) -> MockConfigEntry:
    """Set up a BetaSeries entry backed by the given mocked client.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        mock_client (AsyncMock): The client mock to inject.

    Returns:
        MockConfigEntry: The set-up config entry.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_refresh_buttons_disabled_by_default(hass: HomeAssistant) -> None:
    """Disable both refresh buttons by default, as diagnostic entities."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    await _async_setup(hass, mock_client)

    registry = er.async_get(hass)
    for entity_id in (
        "button.betaseries_test_user_refresh_badges",
        "button.betaseries_test_user_refresh_planning",
    ):
        assert hass.states.get(entity_id) is None
        entity_entry = registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entity_entry.entity_category == "diagnostic"


async def test_refresh_badges_button_presses_force_refresh(hass: HomeAssistant) -> None:
    """Call MemberCoordinator.async_force_refresh_badges() when the button is pressed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    entry = await _async_setup(hass, mock_client)

    entity_id = "button.betaseries_test_user_refresh_badges"
    er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.betaseries.coordinator.MemberCoordinator.async_force_refresh_badges",
        new_callable=AsyncMock,
    ) as mock_force_refresh:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": entity_id}, blocking=True
        )

    mock_force_refresh.assert_awaited_once()


async def test_refresh_planning_button_presses_force_refresh(hass: HomeAssistant) -> None:
    """Call PlanningCoordinator.async_force_refresh_planning() when the button is pressed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    entry = await _async_setup(hass, mock_client)

    entity_id = "button.betaseries_test_user_refresh_planning"
    er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.betaseries.coordinator.PlanningCoordinator.async_force_refresh_planning",
        new_callable=AsyncMock,
    ) as mock_force_refresh:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": entity_id}, blocking=True
        )

    mock_force_refresh.assert_awaited_once()
