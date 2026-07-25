"""Tests for BetaSeriesEntity (base entity)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator
from custom_components.betaseries.entity import BetaSeriesEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers.entity import EntityDescription

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ENTITY_DESCRIPTION = EntityDescription(key="episodes_to_watch")


async def test_unique_id_and_device_info(hass: HomeAssistant) -> None:
    """Derive unique_id and device info from the config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user")
    entry.add_to_hass(hass)
    coordinator = MemberCoordinator(hass, entry, AsyncMock())

    entity = BetaSeriesEntity(coordinator, ENTITY_DESCRIPTION)

    assert entity.unique_id == "42_episodes_to_watch"
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {(DOMAIN, "42")}
    assert entity.device_info["name"] == "BetaSeries - test_user"
    assert entity.device_info["manufacturer"] == "BetaSeries"
