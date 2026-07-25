"""Tests for the BetaSeries options flow (scan interval settings)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.betaseries.const import (
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_SCAN_INTERVAL,
    DOMAIN,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register a mock config entry.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.

    Returns:
        MockConfigEntry: The registered config entry.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", data=USER_INPUT)
    entry.add_to_hass(hass)
    return entry


async def test_options_flow_shows_current_defaults(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Show the form pre-filled with the default scan intervals."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"] is not None
    schema_defaults = {key.schema: key.default() for key in result["data_schema"].schema}
    assert schema_defaults[CONF_MEMBER_SCAN_INTERVAL] == 15
    assert schema_defaults[CONF_PLANNING_SCAN_INTERVAL] == 60


async def test_options_flow_updates_intervals(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Persist the submitted scan intervals as the entry's options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MEMBER_SCAN_INTERVAL: 30, CONF_PLANNING_SCAN_INTERVAL: 120},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_MEMBER_SCAN_INTERVAL: 30, CONF_PLANNING_SCAN_INTERVAL: 120}


async def test_options_flow_shows_previously_saved_values(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Pre-fill the form with previously saved options, not the defaults."""
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_MEMBER_SCAN_INTERVAL: 45, CONF_PLANNING_SCAN_INTERVAL: 180}
    )

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["data_schema"] is not None
    schema_defaults = {key.schema: key.default() for key in result["data_schema"].schema}
    assert schema_defaults[CONF_MEMBER_SCAN_INTERVAL] == 45
    assert schema_defaults[CONF_PLANNING_SCAN_INTERVAL] == 180


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (CONF_MEMBER_SCAN_INTERVAL, 4),
        (CONF_MEMBER_SCAN_INTERVAL, 121),
        (CONF_PLANNING_SCAN_INTERVAL, 14),
        (CONF_PLANNING_SCAN_INTERVAL, 361),
    ],
)
async def test_options_flow_rejects_out_of_range_values(
    hass: HomeAssistant, config_entry: MockConfigEntry, field: str, value: int
) -> None:
    """Reject scan interval values outside their allowed range.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        config_entry (MockConfigEntry): The registered config entry.
        field (str): The option key being tested out of range.
        value (int): The out-of-range value submitted for that key.

    """
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    user_input = {CONF_MEMBER_SCAN_INTERVAL: 15, CONF_PLANNING_SCAN_INTERVAL: 60, field: value}

    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(result["flow_id"], user_input)
