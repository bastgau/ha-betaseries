"""Tests for the BetaSeries options flow (scan interval and months window settings)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    CONF_UPCOMING_MEDIA_CARD,
    DEFAULT_LOCALE,
    DOMAIN,
)
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType, section

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}
SAVED_DATA = {CONF_API_KEY: "test-api-key", "access_token": "token123"}

# Where each option field sits in the form. The form nests its fields under
# one section per coordinator, so a flat submission is rejected whatever its
# values: tests that expect a rejection must send the real shape, or they
# would pass on the shape alone.
_FIELD_SECTIONS = {
    CONF_MEMBER_SCAN_INTERVAL: SECTION_MEMBER,
    CONF_PLANNING_SCAN_INTERVAL: SECTION_PLANNING,
    CONF_PLANNING_MONTHS_BEHIND: SECTION_PLANNING,
    CONF_PLANNING_MONTHS_AHEAD: SECTION_PLANNING,
    CONF_EPISODES_SCAN_INTERVAL: SECTION_EPISODES,
    CONF_SHOWS_LIMIT: SECTION_EPISODES,
    CONF_EPISODES_LIMIT: SECTION_EPISODES,
    CONF_UPCOMING_MEDIA_CARD: SECTION_EPISODES,
}


def _form_input(**overrides: object) -> dict[str, Any]:
    """Build a valid sectioned form submission from the defaults, with some fields overridden."""
    fields: dict[str, object] = {
        CONF_MEMBER_SCAN_INTERVAL: 15,
        CONF_PLANNING_SCAN_INTERVAL: 60,
        CONF_PLANNING_MONTHS_BEHIND: 2,
        CONF_PLANNING_MONTHS_AHEAD: 2,
        CONF_EPISODES_SCAN_INTERVAL: 30,
        CONF_SHOWS_LIMIT: 10,
        CONF_EPISODES_LIMIT: 2,
        CONF_UPCOMING_MEDIA_CARD: False,
        CONF_LOCALE: DEFAULT_LOCALE,
        **overrides,
    }
    user_input: dict[str, Any] = {}
    for field, value in fields.items():
        section_key = _FIELD_SECTIONS.get(field)
        if section_key is None:
            user_input[field] = value
        else:
            user_input.setdefault(section_key, {})[field] = value
    return user_input


def _section_defaults(schema: probatio.Schema) -> dict[str, object]:
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
    assert schema_defaults[CONF_UPCOMING_MEDIA_CARD] is False
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
            CONF_UPCOMING_MEDIA_CARD: True,
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
        CONF_UPCOMING_MEDIA_CARD: True,
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
            CONF_UPCOMING_MEDIA_CARD: True,
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
    assert schema_defaults[CONF_UPCOMING_MEDIA_CARD] is True
    assert schema_defaults[CONF_PLANNING_MONTHS_BEHIND] == 1
    assert schema_defaults[CONF_PLANNING_MONTHS_AHEAD] == 4
    assert schema_defaults[CONF_LOCALE] == "en"


# Both ends of every range, as the form's labels announce them (see
# strings.json). Literal values rather than const.py's MIN_/MAX_ names, so a
# bound changed in const.py without its label fails here.
_RANGES = {
    CONF_MEMBER_SCAN_INTERVAL: (5, 120),
    CONF_PLANNING_SCAN_INTERVAL: (15, 360),
    # The two directions do not share a ceiling: a past month is fetched once
    # then cached, a future one on every refresh (see const.py).
    CONF_PLANNING_MONTHS_BEHIND: (0, 24),
    CONF_PLANNING_MONTHS_AHEAD: (0, 2),
    CONF_EPISODES_SCAN_INTERVAL: (5, 120),
    CONF_SHOWS_LIMIT: (1, 300),
    CONF_EPISODES_LIMIT: (1, 10),
}


@pytest.mark.parametrize(
    ("field", "value"),
    [(field, bound) for field, bounds in _RANGES.items() for bound in bounds],
)
async def test_options_flow_accepts_range_bounds(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    field: str,
    value: int,
) -> None:
    """Accept each numeric option at either end of its range."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(result["flow_id"], _form_input(**{field: value}))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[field] == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        *((field, low - 1) for field, (low, _) in _RANGES.items()),
        *((field, high + 1) for field, (_, high) in _RANGES.items()),
        (CONF_LOCALE, "es"),
    ],
)
async def test_options_flow_rejects_out_of_range_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    field: str,
    value: int | str,
) -> None:
    """Reject each numeric option just outside its range, and an invalid locale."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Matching on the field proves the rejection is about this value, not
    # about the shape of the submission.
    with pytest.raises(probatio.Invalid, match=field):
        await hass.config_entries.options.async_configure(result["flow_id"], _form_input(**{field: value}))
