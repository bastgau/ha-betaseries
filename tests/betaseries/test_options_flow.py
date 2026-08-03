"""Tests for the BetaSeries options flow (scan interval and months window settings)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.betaseries.config_flow import SECTION_EPISODES, SECTION_MEMBER, SECTION_PLANNING
from custom_components.betaseries.const import (
    CONF_EPISODES_LIMIT,
    CONF_EPISODES_SCAN_INTERVAL,
    CONF_LOCALE,
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    CONF_SHOWS_LIMIT,
    DEFAULT_LOCALE,
    DOMAIN,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType, section

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}

DEFAULT_USER_INPUT = {
    CONF_MEMBER_SCAN_INTERVAL: 15,
    CONF_PLANNING_SCAN_INTERVAL: 60,
    CONF_EPISODES_SCAN_INTERVAL: 30,
    CONF_SHOWS_LIMIT: 10,
    CONF_EPISODES_LIMIT: 2,
    CONF_PLANNING_MONTHS_BEHIND: 2,
    CONF_PLANNING_MONTHS_AHEAD: 2,
    CONF_LOCALE: DEFAULT_LOCALE,
}


def _section_defaults(schema: vol.Schema) -> dict[str, object]:
    """Collect every field's default, looking inside the form's sections."""
    defaults: dict[str, object] = {}
    for key, value in schema.schema.items():
        if isinstance(value, section):
            defaults.update({inner.schema: inner.default() for inner in value.schema.schema})
        else:
            defaults[key.schema] = key.default()
    return defaults


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register a mock config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", data=USER_INPUT)
    entry.add_to_hass(hass)
    return entry


async def test_options_flow_shows_current_defaults(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Show the form pre-filled with the default scan intervals and months window."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"] is not None
    schema_defaults = _section_defaults(result["data_schema"])
    assert schema_defaults[CONF_MEMBER_SCAN_INTERVAL] == 15
    assert schema_defaults[CONF_PLANNING_SCAN_INTERVAL] == 60
    assert schema_defaults[CONF_EPISODES_SCAN_INTERVAL] == 30
    assert schema_defaults[CONF_SHOWS_LIMIT] == 10
    assert schema_defaults[CONF_EPISODES_LIMIT] == 2
    assert schema_defaults[CONF_PLANNING_MONTHS_BEHIND] == 2
    assert schema_defaults[CONF_PLANNING_MONTHS_AHEAD] == 2
    assert schema_defaults[CONF_LOCALE] == DEFAULT_LOCALE


async def test_options_flow_updates_intervals(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Persist the submitted scan intervals and months window as the entry's options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # The form nests its fields under one section per coordinator...
    user_input = {
        SECTION_MEMBER: {CONF_MEMBER_SCAN_INTERVAL: 30},
        SECTION_PLANNING: {
            CONF_PLANNING_SCAN_INTERVAL: 120,
            CONF_PLANNING_MONTHS_BEHIND: 3,
            CONF_PLANNING_MONTHS_AHEAD: 1,
        },
        SECTION_EPISODES: {
            CONF_EPISODES_SCAN_INTERVAL: 45,
            CONF_SHOWS_LIMIT: 5,
            CONF_EPISODES_LIMIT: 3,
        },
        CONF_LOCALE: "en",
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # ... but they are stored flat, so the coordinators read them unchanged.
    assert config_entry.options == {
        CONF_MEMBER_SCAN_INTERVAL: 30,
        CONF_PLANNING_SCAN_INTERVAL: 120,
        CONF_PLANNING_MONTHS_BEHIND: 3,
        CONF_PLANNING_MONTHS_AHEAD: 1,
        CONF_EPISODES_SCAN_INTERVAL: 45,
        CONF_SHOWS_LIMIT: 5,
        CONF_EPISODES_LIMIT: 3,
        CONF_LOCALE: "en",
    }


async def test_options_flow_shows_previously_saved_values(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:  # pylint: disable=redefined-outer-name
    """Pre-fill the form with previously saved options, not the defaults."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_MEMBER_SCAN_INTERVAL: 45,
            CONF_PLANNING_SCAN_INTERVAL: 180,
            CONF_EPISODES_SCAN_INTERVAL: 60,
            CONF_SHOWS_LIMIT: 20,
            CONF_EPISODES_LIMIT: 1,
            CONF_PLANNING_MONTHS_BEHIND: 1,
            CONF_PLANNING_MONTHS_AHEAD: 4,
            CONF_LOCALE: "en",
        },
    )

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["data_schema"] is not None
    schema_defaults = _section_defaults(result["data_schema"])
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
        # 4 is the first rejected value on both: the month window is capped at
        # 3 either way (see const.py).
        (CONF_PLANNING_MONTHS_BEHIND, -1),
        (CONF_PLANNING_MONTHS_BEHIND, 4),
        (CONF_PLANNING_MONTHS_AHEAD, -1),
        (CONF_PLANNING_MONTHS_AHEAD, 4),
        (CONF_LOCALE, "es"),
    ],
)
async def test_options_flow_rejects_out_of_range_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    field: str,
    value: int | str,
) -> None:
    """Reject scan interval/months window values outside their allowed range, and an invalid locale."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    user_input = {**DEFAULT_USER_INPUT, field: value}

    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(result["flow_id"], user_input)
