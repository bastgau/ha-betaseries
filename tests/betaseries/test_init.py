"""Tests for BetaSeries async_setup_entry / async_unload_entry."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from custom_components.betaseries.betaseries.exceptions import Error
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import CONF_LOCALE, DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator, PlanningCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from tests.conftest import client_mock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret"}

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


async def test_setup_entry_creates_coordinator(hass: HomeAssistant) -> None:
    """Set up the entry, populating runtime_data with a refreshed MemberCoordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert isinstance(entry.runtime_data.member, MemberCoordinator)
    assert entry.runtime_data.member.data == MEMBER_DATA
    assert isinstance(entry.runtime_data.planning, PlanningCoordinator)
    assert not tuple(entry.runtime_data.planning.data)


async def test_setup_entry_succeeds_when_only_the_planning_fails(hass: HomeAssistant) -> None:
    """Load the entry even if the planning cannot be fetched.

    The planning issues one request per month in the window against a single
    one for the member data, so it is the likelier of the two to fail. A
    planning outage must degrade to unavailable calendar/next episode
    entities rather than take every member sensor down with it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.side_effect = Error("planning is down")

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Member data is there, so its sensors work...
    assert entry.runtime_data.member.last_update_success
    assert entry.runtime_data.member.data == MEMBER_DATA
    # ... while the planning-backed entities mark themselves unavailable.
    assert not entry.runtime_data.planning.last_update_success

    state = hass.states.get("sensor.betaseries_test_user_episodes_to_watch")
    assert state is not None
    assert state.state == "12"

    # The planning-backed entities still exist - they just report unavailable
    # rather than failing to be added at all (their properties are read while
    # HA adds them, before any planning data exists).
    for entity_id in (
        "calendar.betaseries_test_user_release_calendar",
        "sensor.betaseries_test_user_latest_unwatched_episode",
    ):
        planning_state = hass.states.get(entity_id)
        assert planning_state is not None, entity_id
        assert planning_state.state == STATE_UNAVAILABLE, entity_id

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None
    assert entity.event is None
    assert await entity.async_get_events(hass, dt_util.now(), dt_util.now() + timedelta(days=30)) == []

    # Diagnostic sensor, disabled by default: enable it and reload so its own
    # guards are exercised too.
    registry = er.async_get(hass)
    registry.async_update_entity("sensor.betaseries_test_user_calendar_event_count", disabled_by=None)
    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    count_entity = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.betaseries_test_user_calendar_event_count"
    )
    assert count_entity is not None
    assert count_entity.native_value is None
    assert count_entity.extra_state_attributes == {}

    latest_unwatched = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.betaseries_test_user_latest_unwatched_episode"
    )
    assert latest_unwatched is not None
    assert latest_unwatched.native_value is None
    assert latest_unwatched.extra_state_attributes is None


async def test_setup_entry_retries_when_the_member_data_fails(hass: HomeAssistant) -> None:
    """Fail the whole setup when the member data cannot be fetched.

    Unlike the planning, the member data backs every sensor and is the single
    request proving the stored credentials still work, so its failure must
    raise ConfigEntryNotReady and have HA retry the entry later.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.side_effect = Error("member endpoint is down")

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_passes_default_locale_to_client(hass: HomeAssistant) -> None:
    """Construct the Client with DEFAULT_LOCALE when the entry has no locale option set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client) as mock_client_class:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client_class.call_args.args[-1] == "fr"


async def test_setup_entry_passes_configured_locale_to_client(hass: HomeAssistant) -> None:
    """Construct the Client with the entry's configured locale option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
        options={CONF_LOCALE: "en"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client) as mock_client_class:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_client_class.call_args.args[-1] == "en"


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Unload a previously set up entry successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**USER_INPUT, "access_token": "token123"},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
