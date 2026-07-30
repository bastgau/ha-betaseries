"""Tests for the BetaSeries calendar entity."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.const import CONF_PLANNING_MONTHS_BEHIND, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}

EARLIER_EPISODE = Episode(
    id="999",
    season=3,
    number=3,
    code="S03E03",
    title="An Earlier Episode",
    description="An earlier episode summary.",
    air_date=date(2026, 8, 1),
    seen=False,
    platforms=("Netflix",),
    resource_url="https://www.betaseries.com/episode/999",
    show=Show(id="55", title="Example Show"),
)

LATER_EPISODE = Episode(
    id="1001",
    season=3,
    number=4,
    code="S03E04",
    title="The One With The Tests",
    description="A thrilling episode summary.",
    air_date=date(2026, 8, 10),
    seen=False,
    platforms=("Netflix", "Apple TV"),
    resource_url="https://www.betaseries.com/episode/1001",
    show=Show(id="55", title="Example Show"),
)

MEMBER_DATA = MemberData(
    identity=MemberIdentity(id="42", login="test_user"),
    stats=MemberStats(
        xp=1337,
        episodes_to_watch=0,
        time_to_spend=0,
        progress=0,
        shows_to_watch=0,
        movies_to_watch=0,
        shows_current=0,
        badges=0,
        shows=0,
        shows_finished=0,
        episodes=0,
        time_on_tv=0,
        movies=0,
        streak_days=0,
        member_since_days=0,
        episodes_per_month=0,
        favorite_genre="Drama",
    ),
)


async def _setup_entry_with_planning(hass: HomeAssistant, episodes: tuple[Episode, ...]) -> MockConfigEntry:
    """Set up a config entry with a mocked planning response.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        episodes (tuple[Episode, ...]): Episodes returned for the first fetch_planning() call.

    Returns:
        MockConfigEntry: The set up config entry.

    """
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
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode(episodes),
        CollectionEpisode(()),
        CollectionEpisode(()),
    ]

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_calendar_lists_events_sorted_by_air_date(hass: HomeAssistant) -> None:
    """Expose one all-day event per unseen episode, sorted by air_date."""
    await _setup_entry_with_planning(hass, (LATER_EPISODE, EARLIER_EPISODE))

    state = hass.states.get("calendar.betaseries_test_user_release_calendar")
    assert state is not None
    assert state.attributes["message"] == "Example Show - S03E03"


async def test_calendar_event_is_none_when_no_episodes(hass: HomeAssistant) -> None:
    """Report no event when the planning is empty."""
    await _setup_entry_with_planning(hass, ())

    state = hass.states.get("calendar.betaseries_test_user_release_calendar")
    assert state is not None
    assert state.state == "off"


async def test_calendar_event_skips_seen_episodes(hass: HomeAssistant) -> None:
    """Skip already-seen episodes when picking the next event."""
    seen_episode = Episode(
        id="500",
        season=3,
        number=2,
        code="S03E02",
        title="Already Watched",
        description="",
        air_date=date(2026, 7, 25),
        seen=True,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/500",
        show=Show(id="55", title="Example Show"),
    )
    await _setup_entry_with_planning(hass, (seen_episode, EARLIER_EPISODE, LATER_EPISODE))

    state = hass.states.get("calendar.betaseries_test_user_release_calendar")
    assert state is not None
    assert state.attributes["message"] == "Example Show - S03E03"


async def test_async_get_events_includes_seen_episodes(hass: HomeAssistant) -> None:
    """Include already-seen episodes when listing events over a range."""
    seen_episode = Episode(
        id="500",
        season=3,
        number=2,
        code="S03E02",
        title="Already Watched",
        description="",
        air_date=date(2026, 8, 5),
        seen=True,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/500",
        show=Show(id="55", title="Example Show"),
    )
    entry = await _setup_entry_with_planning(hass, (seen_episode, EARLIER_EPISODE, LATER_EPISODE))

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None

    tz = dt_util.get_default_time_zone()
    start = datetime(2026, 8, 1, tzinfo=tz)
    end = datetime(2026, 8, 31, tzinfo=tz)
    events = await entity.async_get_events(hass, start, end)

    assert {event.uid for event in events} == {"999", "500", "1001"}

    await hass.config_entries.async_unload(entry.entry_id)


async def test_async_get_events_filters_by_range(hass: HomeAssistant) -> None:
    """Return only events overlapping the requested range."""
    entry = await _setup_entry_with_planning(hass, (EARLIER_EPISODE, LATER_EPISODE))

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None

    tz = dt_util.get_default_time_zone()
    start = datetime(2026, 8, 5, tzinfo=tz)
    end = datetime(2026, 8, 31, tzinfo=tz)
    events = await entity.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Example Show - S03E04"
    assert events[0].uid == "1001"
    assert events[0].description == "The One With The Tests\n\nA thrilling episode summary.\n\nNetflix, Apple TV"
    assert events[0].location == "https://www.betaseries.com/episode/1001"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_async_get_events_converts_utc_bounds_to_local(hass: HomeAssistant) -> None:
    """Compare the requested range in local time, not UTC.

    HA passes tz-aware bounds, usually in UTC: local midnight in a positive
    offset zone is the previous day in UTC. Reducing the end bound to a date
    without converting it back to local time first pulls it a day earlier,
    dropping any episode airing on the last day of the requested range.
    """
    await hass.config.async_set_time_zone("Europe/Paris")
    entry = await _setup_entry_with_planning(hass, (EARLIER_EPISODE, LATER_EPISODE))

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None

    # Local midnight on both ends, as HA sends them: expressed in UTC.
    # LATER_EPISODE airs on 2026-08-10, the exact last day of the range.
    tz = dt_util.get_default_time_zone()
    start = dt_util.as_utc(datetime(2026, 8, 1, tzinfo=tz))
    end = dt_util.as_utc(datetime(2026, 8, 10, tzinfo=tz))
    assert end.date() == date(2026, 8, 9)  # guard: the bound really is shifted in UTC

    events = await entity.async_get_events(hass, start, end)

    # Without the conversion, the end bound would be 2026-08-09 and drop "1001".
    assert {event.uid for event in events} == {"999", "1001"}

    await hass.config_entries.async_unload(entry.entry_id)


async def test_calendar_event_description_without_platforms_or_description(hass: HomeAssistant) -> None:
    """Omit the summary/platforms lines when neither is known."""
    episode = Episode(
        id="2002",
        season=1,
        number=1,
        code="S01E01",
        title="No Platforms",
        description="",
        air_date=date(2026, 8, 1),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/2002",
        show=Show(id="55", title="Example Show"),
    )
    entry = await _setup_entry_with_planning(hass, (episode,))

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None
    assert entity.event is not None
    assert entity.event.description == "No Platforms"
    assert entity.event.location == "https://www.betaseries.com/episode/2002"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_calendar_event_description_falls_back_to_show_description(hass: HomeAssistant) -> None:
    """Use the show's synopsis when the episode has no description of its own.

    Regression test for a real payload shape (bruno/Planning/member.bru): a
    not-yet-aired episode's own "description" is empty, but its show's is not.
    """
    episode = Episode(
        id="3003",
        season=1,
        number=1,
        code="S01E01",
        title="Not Aired Yet",
        description="",
        air_date=date(2026, 8, 1),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/3003",
        show=Show(id="55", title="Example Show", description="A show about a silo."),
    )
    entry = await _setup_entry_with_planning(hass, (episode,))

    entity = hass.data["entity_components"]["calendar"].get_entity("calendar.betaseries_test_user_release_calendar")
    assert entity is not None
    assert entity.event is not None
    assert entity.event.description == "Not Aired Yet\n\nA show about a silo."

    await hass.config_entries.async_unload(entry.entry_id)
