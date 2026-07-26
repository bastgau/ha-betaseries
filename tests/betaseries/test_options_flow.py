"""Tests for the BetaSeries options flow (scan interval and months window settings)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.betaseries.const import (
    CONF_LOCALE,
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    DEFAULT_LOCALE,
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

DEFAULT_USER_INPUT = {
    CONF_MEMBER_SCAN_INTERVAL: 15,
    CONF_PLANNING_SCAN_INTERVAL: 60,
    CONF_PLANNING_MONTHS_BEHIND: 2,
    CONF_PLANNING_MONTHS_AHEAD: 2,
    CONF_LOCALE: DEFAULT_LOCALE,
}


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


async def test_options_flow_shows_current_defaults(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Show the form pre-filled with the default scan intervals and months window."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"] is not None
    schema_defaults = {key.schema: key.default() for key in result["data_schema"].schema}
    assert schema_defaults[CONF_MEMBER_SCAN_INTERVAL] == 15
    assert schema_defaults[CONF_PLANNING_SCAN_INTERVAL] == 60
    assert schema_defaults[CONF_PLANNING_MONTHS_BEHIND] == 2
    assert schema_defaults[CONF_PLANNING_MONTHS_AHEAD] == 2
    assert schema_defaults[CONF_LOCALE] == DEFAULT_LOCALE


async def test_options_flow_updates_intervals(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Persist the submitted scan intervals and months window as the entry's options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    user_input = {
        CONF_MEMBER_SCAN_INTERVAL: 30,
        CONF_PLANNING_SCAN_INTERVAL: 120,
        CONF_PLANNING_MONTHS_BEHIND: 3,
        CONF_PLANNING_MONTHS_AHEAD: 1,
        CONF_LOCALE: "en",
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == user_input


async def test_options_flow_shows_previously_saved_values(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Pre-fill the form with previously saved options, not the defaults."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MEMBER_SCAN_INTERVAL: 45,
            CONF_PLANNING_SCAN_INTERVAL: 180,
            CONF_PLANNING_MONTHS_BEHIND: 1,
            CONF_PLANNING_MONTHS_AHEAD: 4,
            CONF_LOCALE: "en",
        },
    )

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["data_schema"] is not None
    schema_defaults = {key.schema: key.default() for key in result["data_schema"].schema}
    assert schema_defaults[CONF_MEMBER_SCAN_INTERVAL] == 45
    assert schema_defaults[CONF_PLANNING_SCAN_INTERVAL] == 180
    assert schema_defaults[CONF_PLANNING_MONTHS_BEHIND] == 1
    assert schema_defaults[CONF_PLANNING_MONTHS_AHEAD] == 4
    assert schema_defaults[CONF_LOCALE] == "en"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (CONF_MEMBER_SCAN_INTERVAL, 4),
        (CONF_MEMBER_SCAN_INTERVAL, 121),
        (CONF_PLANNING_SCAN_INTERVAL, 14),
        (CONF_PLANNING_SCAN_INTERVAL, 361),
        (CONF_PLANNING_MONTHS_BEHIND, -1),
        (CONF_PLANNING_MONTHS_BEHIND, 13),
        (CONF_PLANNING_MONTHS_AHEAD, -1),
        (CONF_PLANNING_MONTHS_AHEAD, 13),
        (CONF_LOCALE, "es"),
    ],
)
async def test_options_flow_rejects_out_of_range_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    field: str,
    value: int | str,
) -> None:
    """Reject scan interval/months window values outside their allowed range, and an invalid locale.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        config_entry (MockConfigEntry): The registered config entry.
        field (str): The option key being tested out of range.
        value (int | str): The invalid value submitted for that key.

    """
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    user_input = {**DEFAULT_USER_INPUT, field: value}

    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(result["flow_id"], user_input)
