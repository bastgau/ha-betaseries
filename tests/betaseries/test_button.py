"""Tests for BetaSeries button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.helpers import entity_registry as er
from tests.conftest import client_mock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}
SAVED_DATA = {CONF_API_KEY: "test-api-key", "access_token": "token123"}

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
    """Set up a BetaSeries entry backed by the given mocked client."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_clear_cache_buttons_disabled_by_default(hass: HomeAssistant) -> None:
    """Disable every refresh button by default, as diagnostic entities."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    await _async_setup(hass, mock_client)

    registry = er.async_get(hass)
    for entity_id in (
        "button.betaseries_test_user_clear_badges_cache",
        "button.betaseries_test_user_clear_planning_cache",
        "button.betaseries_test_user_clear_shows_to_catch_up_cache",
    ):
        assert hass.states.get(entity_id) is None
        entity_entry = registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entity_entry.entity_category == "diagnostic"


async def test_clear_badges_cache_button_clears_and_refreshes(hass: HomeAssistant) -> None:
    """Call MemberCoordinator.async_clear_badges_cache() when the button is pressed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    entry = await _async_setup(hass, mock_client)

    entity_id = "button.betaseries_test_user_clear_badges_cache"
    er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.betaseries.coordinator.MemberCoordinator.async_clear_badges_cache",
        new_callable=AsyncMock,
    ) as mock_clear_cache:
        await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": entity_id}, blocking=True)

    mock_clear_cache.assert_awaited_once()


async def test_clear_planning_cache_button_clears_and_refreshes(hass: HomeAssistant) -> None:
    """Call PlanningCoordinator.async_clear_planning_cache() when the button is pressed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    entry = await _async_setup(hass, mock_client)

    entity_id = "button.betaseries_test_user_clear_planning_cache"
    er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.betaseries.coordinator.PlanningCoordinator.async_clear_planning_cache",
        new_callable=AsyncMock,
    ) as mock_clear_cache:
        await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": entity_id}, blocking=True)

    mock_clear_cache.assert_awaited_once()


async def test_clear_watch_list_cache_button_clears_and_refreshes(hass: HomeAssistant) -> None:
    """Call WatchListCoordinator.async_clear_watch_list_cache() when the button is pressed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    await _async_setup(hass, mock_client)

    entity_id = "button.betaseries_test_user_clear_shows_to_catch_up_cache"
    er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        await hass.config_entries.async_reload(next(iter(hass.config_entries.async_entries(DOMAIN))).entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.betaseries.coordinator.WatchListCoordinator.async_clear_watch_list_cache",
        new_callable=AsyncMock,
    ) as mock_clear_cache:
        await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": entity_id}, blocking=True)

    mock_clear_cache.assert_awaited_once()


async def test_clear_watch_list_cache_clears_the_show_images_cache(hass: HomeAssistant) -> None:
    """Drop the cached artwork so it is refetched, unlike on a regular refresh."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    entry = await _async_setup(hass, mock_client)

    coordinator = entry.runtime_data.watch_list
    with patch.object(coordinator.show_images_store, "async_remove", new_callable=AsyncMock) as mock_remove:
        await coordinator.async_clear_watch_list_cache()

    mock_remove.assert_awaited_once()
    assert coordinator.last_update_success is True
