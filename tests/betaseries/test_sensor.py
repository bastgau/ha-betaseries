"""Tests for BetaSeries sensor entities."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.planning_episode import PlanningEpisode
from custom_components.betaseries.const import CONF_PLANNING_MONTHS_AHEAD, CONF_PLANNING_MONTHS_BEHIND, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}

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


async def test_sensors_reflect_member_data(hass: HomeAssistant) -> None:
    """Set up the entry and expose all 17 sensors with the fetched values."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    expected_states = {
        "sensor.betaseries_test_user_episodes_to_watch": "12",
        "sensor.betaseries_test_user_time_to_spend": "540",
        "sensor.betaseries_test_user_progress": "77.4699",
        "sensor.betaseries_test_user_shows_to_watch": "3",
        "sensor.betaseries_test_user_movies_to_watch": "2",
        "sensor.betaseries_test_user_shows_current": "5",
        "sensor.betaseries_test_user_badges": "8",
        "sensor.betaseries_test_user_shows_total": "40",
        "sensor.betaseries_test_user_shows_finished": "30",
        "sensor.betaseries_test_user_episodes_watched": "1200",
        "sensor.betaseries_test_user_time_on_tv": "54000",
        "sensor.betaseries_test_user_movies_total": "100",
        "sensor.betaseries_test_user_xp": "1337",
        "sensor.betaseries_test_user_streak_days": "15",
        "sensor.betaseries_test_user_member_since": "3650",
        "sensor.betaseries_test_user_episodes_per_month": "25.5",
        "sensor.betaseries_test_user_favorite_genre": "Drama",
    }

    for entity_id, expected_state in expected_states.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == expected_state


async def test_next_episode_reflects_earliest_unseen_episode(hass: HomeAssistant) -> None:
    """Expose the earliest unseen episode's air date as a local-midnight timestamp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=USER_INPUT,
        options={CONF_PLANNING_MONTHS_BEHIND: 0},
    )
    entry.add_to_hass(hass)

    episode = PlanningEpisode(
        id="1001",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=4,
        code="S03E04",
        title="The One With The Tests",
        description="A thrilling episode summary.",
        air_date=date(2026, 8, 10),
        seen=False,
        platforms=("Netflix",),
        resource_url="https://www.betaseries.com/episode/1001",
    )

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.side_effect = [(episode,), (), ()]

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_next_episode")
    assert state is not None
    assert dt_util.parse_datetime(state.state) == dt_util.start_of_local_day(date(2026, 8, 10))


async def test_next_episode_is_unknown_when_planning_is_empty(hass: HomeAssistant) -> None:
    """Report an unknown state when there is no unseen episode."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_next_episode")
    assert state is not None
    assert state.state == "unknown"


async def test_next_episode_skips_seen_episodes(hass: HomeAssistant) -> None:
    """Skip already-seen episodes when picking the next episode's air date."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=USER_INPUT,
        options={CONF_PLANNING_MONTHS_BEHIND: 0},
    )
    entry.add_to_hass(hass)

    seen_episode = PlanningEpisode(
        id="500",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=2,
        code="S03E02",
        title="Already Watched",
        description="",
        air_date=date(2026, 8, 1),
        seen=True,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/500",
    )
    unseen_episode = PlanningEpisode(
        id="1001",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=4,
        code="S03E04",
        title="The One With The Tests",
        description="A thrilling episode summary.",
        air_date=date(2026, 8, 10),
        seen=False,
        platforms=("Netflix",),
        resource_url="https://www.betaseries.com/episode/1001",
    )

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.side_effect = [(seen_episode, unseen_episode), (), ()]

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_next_episode")
    assert state is not None
    assert dt_util.parse_datetime(state.state) == dt_util.start_of_local_day(date(2026, 8, 10))


async def test_calendar_event_count_disabled_by_default(hass: HomeAssistant) -> None:
    """Disable the diagnostic Calendar event count sensor by default."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.betaseries_test_user_calendar_event_count") is None

    registry = er.async_get(hass)
    entity_entry = registry.async_get("sensor.betaseries_test_user_calendar_event_count")
    assert entity_entry is not None
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_calendar_event_count_reports_total_and_breakdown_by_month(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Expose the total episode count and a per-month breakdown as attributes, once enabled."""
    freezer.move_to("2026-08-15")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=USER_INPUT,
        options={CONF_PLANNING_MONTHS_BEHIND: 0, CONF_PLANNING_MONTHS_AHEAD: 1},
    )
    entry.add_to_hass(hass)

    august_episode_1 = PlanningEpisode(
        id="1001",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=4,
        code="S03E04",
        title="Episode A",
        description="",
        air_date=date(2026, 8, 10),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1001",
    )
    august_episode_2 = PlanningEpisode(
        id="1002",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=5,
        code="S03E05",
        title="Episode B",
        description="",
        air_date=date(2026, 8, 20),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1002",
    )
    september_episode = PlanningEpisode(
        id="1003",
        show_id="55",
        show_title="Example Show",
        season=3,
        episode=6,
        code="S03E06",
        title="Episode C",
        description="",
        air_date=date(2026, 9, 5),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1003",
    )

    episodes_by_month: dict[str, tuple[PlanningEpisode, ...]] = {
        "2026-08": (august_episode_1, august_episode_2),
        "2026-09": (september_episode,),
    }

    def _fetch_planning(month: str) -> tuple[PlanningEpisode, ...]:
        return episodes_by_month.get(month, ())

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.side_effect = _fetch_planning

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "sensor.betaseries_test_user_calendar_event_count"
        er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "3"
    assert state.attributes["2026-08"] == 2
    assert state.attributes["2026-09"] == 1


async def test_calendar_event_count_is_zero_when_planning_is_empty(hass: HomeAssistant) -> None:
    """Report zero events and no month attributes when the planning is empty, once enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=USER_INPUT,
        options={CONF_PLANNING_MONTHS_BEHIND: 0},
    )
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = ()

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "sensor.betaseries_test_user_calendar_event_count"
        er.async_get(hass).async_update_entity(entity_id, disabled_by=None)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
