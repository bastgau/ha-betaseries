"""Tests for BetaSeries sensor entities."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from custom_components.betaseries.betaseries.badge import Badge
from custom_components.betaseries.betaseries.collection_badge import CollectionBadge
from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.show_additional_information import ShowAdditionalInformation
from custom_components.betaseries.betaseries.show_images import ShowImages
from custom_components.betaseries.const import CONF_PLANNING_MONTHS_AHEAD, CONF_PLANNING_MONTHS_BEHIND, DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from tests.conftest import client_mock

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

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


async def test_sensors_reflect_member_data(hass: HomeAssistant) -> None:
    """Set up the entry and expose all 17 sensors with the fetched values."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    expected_states = {
        "sensor.betaseries_test_user_episodes_to_watch": "12",
        "sensor.betaseries_test_user_time_to_spend": "540",
        "sensor.betaseries_test_user_progress": "77.4699",
        "sensor.betaseries_test_user_shows_not_started": "3",
        "sensor.betaseries_test_user_movies_to_watch": "2",
        "sensor.betaseries_test_user_shows_in_progress": "5",
        "sensor.betaseries_test_user_badges": "8",
        "sensor.betaseries_test_user_shows_total": "40",
        "sensor.betaseries_test_user_shows_finished": "30",
        "sensor.betaseries_test_user_episodes_watched": "1200",
        "sensor.betaseries_test_user_time_on_tv": "54000",
        "sensor.betaseries_test_user_movies_total": "100",
        "sensor.betaseries_test_user_xp": "1337",
        "sensor.betaseries_test_user_streak_days": "15",
        "sensor.betaseries_test_user_membership_duration": "3650",
        "sensor.betaseries_test_user_episodes_per_month": "25.5",
        "sensor.betaseries_test_user_favorite_genre": "Drama",
    }

    for entity_id, expected_state in expected_states.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == expected_state


def _end_of_local_day(day: date) -> datetime:
    """Return the last second of a local day, as the airing sensor timestamps it.

    Args:
        day (date): The day to timestamp.

    Returns:
        datetime: 23:59:59 local time on that day.

    """
    return dt_util.start_of_local_day(day) + timedelta(days=1) - timedelta(seconds=1)


def _episode(  # noqa: PLR0913 -- a test builder, every extra argument is an optional knob
    episode_id: str,
    air_date: date,
    *,
    seen: bool,
    code: str = "S03E04",
    number: int = 4,
    show: Show | None = None,
) -> Episode:
    """Build an Episode for the planning sensor tests.

    Args:
        episode_id (str): BetaSeries episode id.
        air_date (date): Date the episode airs.
        seen (bool): Whether the member has already watched it.
        code (str): Season/episode code.
        number (int): Episode number within the season.
        show (Show | None): Show the episode belongs to, or None for the default one.

    Returns:
        Episode: The built episode.

    """
    return Episode(
        id=episode_id,
        season=3,
        number=number,
        code=code,
        title="The One With The Tests",
        description="A thrilling episode summary.",
        air_date=air_date,
        seen=seen,
        platforms=("Netflix", "Apple TV"),
        resource_url=f"https://www.betaseries.com/episode/{episode_id}",
        show=show or Show(id="55", title="Example Show"),
    )


def _rated_shows(ratings: dict[str, float]) -> CollectionShow:
    """Build the GET /shows/display result carrying each show's member rating.

    Only notes_mean matters here; the rest is filled with the neutral values
    a show with no details would report.

    Args:
        ratings (dict[str, float]): Rating to give each show id.

    Returns:
        CollectionShow: The shows, with their additional information populated.

    """
    return CollectionShow(
        {
            show_id: Show(
                id=show_id,
                title=f"Show {show_id}",
                additional_information=ShowAdditionalInformation(
                    original_title=f"Show {show_id}",
                    imdb_id=None,
                    themoviedb_id=None,
                    genres=(),
                    showrunners=(),
                    aliases=(),
                    seasons=1,
                    followers=0,
                    network="Netflix",
                    country=None,
                    original_language=None,
                    length=30,
                    rating="",
                    notes_mean=rating,
                    notes_total=1,
                    next_trailer=None,
                    resource_url=f"https://www.betaseries.com/serie/show-{show_id}",
                    images=ShowImages(show=None, banner=None, box=None, poster=None, clearlogo=None),
                ),
            )
            for show_id, rating in ratings.items()
        }
    )


async def _setup_with_planning(
    hass: HomeAssistant, episodes: tuple[Episode, ...], shows: CollectionShow | None = None
) -> MockConfigEntry:
    """Set up an entry whose first planning month returns the given episodes.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        episodes (tuple[Episode, ...]): Episodes returned for the first fetch_planning() call.
        shows (CollectionShow | None): Shows returned by fetch_shows(), or None for none at all.

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

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode(episodes),
        CollectionEpisode(()),
        CollectionEpisode(()),
    ]
    if shows is not None:
        mock_client.fetch_shows.return_value = shows

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_previous_episode_airing_picks_the_most_recently_aired_one(hass: HomeAssistant) -> None:
    """Pick the episode that aired last, mirroring "next episode airing"."""
    today = dt_util.now().date()
    older = _episode("500", today - timedelta(days=10), seen=False, code="S03E02", number=2)
    newer = _episode("1001", today - timedelta(days=1), seen=False)
    await _setup_with_planning(hass, (older, newer))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert dt_util.parse_datetime(state.state) == dt_util.start_of_local_day(today - timedelta(days=1))
    assert state.attributes["episode_id"] == "1001"


async def test_previous_episode_airing_ignores_episodes_that_have_not_aired(hass: HomeAssistant) -> None:
    """Skip episodes airing in the future: they have not come out yet."""
    today = dt_util.now().date()
    aired = _episode("500", today - timedelta(days=2), seen=False, code="S03E02", number=2)
    not_yet_aired = _episode("1001", today + timedelta(days=7), seen=False)
    await _setup_with_planning(hass, (aired, not_yet_aired))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["episode_id"] == "500"
    assert dt_util.parse_datetime(state.state) == dt_util.start_of_local_day(today - timedelta(days=2))


async def test_previous_episode_airing_excludes_an_episode_airing_today(hass: HomeAssistant) -> None:
    """Leave an episode airing today to the "next episode airing" sensor.

    BetaSeries gives no airing time, so an episode dated today may still air
    tonight - counting it as already out would be a guess, and the two
    sensors would point at the same episode all day.
    """
    today = dt_util.now().date()
    await _setup_with_planning(hass, (_episode("1001", today, seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.state == "unknown"


async def test_previous_episode_airing_includes_seen_episodes(hass: HomeAssistant) -> None:
    """Report the last episode out, watched or not.

    This is a release date, not a watch list: filtering on `seen` here would
    also make the sensor depend on the planning cache, which never refreshes
    a past month's watch status.
    """
    today = dt_util.now().date()
    unseen = _episode("1001", today - timedelta(days=10), seen=False, code="S03E02", number=2)
    seen = _episode("500", today - timedelta(days=1), seen=True)
    await _setup_with_planning(hass, (unseen, seen))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert dt_util.parse_datetime(state.state) == dt_util.start_of_local_day(today - timedelta(days=1))
    assert state.attributes["episode_id"] == "500"


async def test_previous_episode_airing_exposes_actionable_attributes(hass: HomeAssistant) -> None:
    """Expose the identifiers the (v3) services target, which CalendarEvent cannot carry."""
    yesterday = dt_util.now().date() - timedelta(days=1)
    await _setup_with_planning(hass, (_episode("1001", yesterday, seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["episode_id"] == "1001"
    assert state.attributes["show_id"] == "55"
    assert state.attributes["code"] == "S03E04"
    assert state.attributes["season"] == 3
    assert state.attributes["number"] == 4
    assert state.attributes["title"] == "The One With The Tests"
    assert state.attributes["show_title"] == "Example Show"
    assert state.attributes["platforms"] == ["Netflix", "Apple TV"]
    assert state.attributes["resource_url"] == "https://www.betaseries.com/episode/1001"


async def test_previous_episode_airing_is_unknown_before_anything_has_aired(hass: HomeAssistant) -> None:
    """Report an unknown state, with no attributes, when nothing has aired yet."""
    await _setup_with_planning(hass, (_episode("500", dt_util.now().date() + timedelta(days=3), seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.state == "unknown"
    assert "episode_id" not in state.attributes


async def test_previous_episode_airing_breaks_a_same_day_tie_on_the_show_rating(hass: HomeAssistant) -> None:
    """Prefer the better-rated show when several episodes aired the same day.

    Air date alone leaves the pick to whatever order the months happened to
    be fetched in, which is not a decision. The rating rides along with the
    artwork on the same GET /shows/display call, so it costs no request.
    """
    yesterday = dt_util.now().date() - timedelta(days=1)
    await _setup_with_planning(
        hass,
        (
            _episode("500", yesterday, seen=False, show=Show(id="55", title="Meh Show")),
            _episode("501", yesterday, seen=False, show=Show(id="66", title="Great Show")),
        ),
        shows=_rated_shows({"55": 2.5, "66": 4.8}),
    )

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["show_id"] == "66"
    assert state.attributes["episode_id"] == "501"


async def test_previous_episode_airing_treats_an_unrated_show_as_zero(hass: HomeAssistant) -> None:
    """Let any rated show beat a show BetaSeries has no rating for.

    A show with no rating reports a mean of 0, which is deliberately not told
    apart from a genuine zero: both simply lose the tie-break.
    """
    yesterday = dt_util.now().date() - timedelta(days=1)
    await _setup_with_planning(
        hass,
        (
            _episode("500", yesterday, seen=False, show=Show(id="55", title="Unrated Show")),
            _episode("501", yesterday, seen=False, show=Show(id="66", title="Barely Rated Show")),
        ),
        shows=_rated_shows({"55": 0.0, "66": 0.4}),
    )

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["show_id"] == "66"


async def test_previous_episode_airing_breaks_an_equal_rating_tie_on_the_highest_id(hass: HomeAssistant) -> None:
    """Fall back to the highest episode id so the pick is always total.

    Ids are compared as numbers, not as strings: "1001" must beat "999".
    """
    yesterday = dt_util.now().date() - timedelta(days=1)
    await _setup_with_planning(
        hass,
        (
            _episode("1001", yesterday, seen=False, show=Show(id="55", title="Show A")),
            _episode("999", yesterday, seen=False, show=Show(id="66", title="Show B")),
        ),
        shows=_rated_shows({"55": 3.0, "66": 3.0}),
    )

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["episode_id"] == "1001"


async def test_next_episode_airing_picks_the_first_future_episode(hass: HomeAssistant) -> None:
    """Pick the next episode due to air, regardless of whether it has been seen."""
    today = dt_util.now().date()
    aired = _episode("500", today - timedelta(days=5), seen=False, code="S03E02", number=2)
    upcoming = _episode("1001", today + timedelta(days=3), seen=True)
    await _setup_with_planning(hass, (aired, upcoming))

    state = hass.states.get("sensor.betaseries_test_user_next_episode_airing")
    assert state is not None
    assert dt_util.parse_datetime(state.state) == _end_of_local_day(today + timedelta(days=3))
    # Seen, yet still selected: this sensor answers "when does it come out".
    assert state.attributes["episode_id"] == "1001"


async def test_next_episode_airing_includes_today(hass: HomeAssistant) -> None:
    """Treat an episode airing today as upcoming, not as past."""
    today = dt_util.now().date()
    await _setup_with_planning(hass, (_episode("1001", today, seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_next_episode_airing")
    assert state is not None
    # 23:59:59, not midnight: an episode airing today must stay in the future
    # all day, otherwise the frontend renders "6 hours ago" at 06:00 under a
    # sensor announcing an upcoming release.
    assert dt_util.parse_datetime(state.state) == _end_of_local_day(today)
    assert dt_util.parse_datetime(state.state) > dt_util.now()


async def test_next_episode_airing_is_unknown_when_everything_has_aired(hass: HomeAssistant) -> None:
    """Report an unknown state when no episode is due to air."""
    today = dt_util.now().date()
    await _setup_with_planning(hass, (_episode("500", today - timedelta(days=5), seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_next_episode_airing")
    assert state is not None
    assert state.state == "unknown"


async def test_calendar_event_count_disabled_by_default(hass: HomeAssistant) -> None:
    """Disable the diagnostic Calendar event count sensor by default."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = CollectionEpisode(())

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

    august_episode_1 = Episode(
        id="1001",
        season=3,
        number=4,
        code="S03E04",
        title="Episode A",
        description="",
        air_date=date(2026, 8, 10),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1001",
        show=Show(id="55", title="Example Show"),
    )
    august_episode_2 = Episode(
        id="1002",
        season=3,
        number=5,
        code="S03E05",
        title="Episode B",
        description="",
        air_date=date(2026, 8, 20),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1002",
        show=Show(id="55", title="Example Show"),
    )
    september_episode = Episode(
        id="1003",
        season=3,
        number=6,
        code="S03E06",
        title="Episode C",
        description="",
        air_date=date(2026, 9, 5),
        seen=False,
        platforms=(),
        resource_url="https://www.betaseries.com/episode/1003",
        show=Show(id="55", title="Example Show"),
    )

    episodes_by_month: dict[str, tuple[Episode, ...]] = {
        "2026-08": (august_episode_1, august_episode_2),
        "2026-09": (september_episode,),
    }

    def _fetch_planning(month: str) -> CollectionEpisode:
        return CollectionEpisode(episodes_by_month.get(month, ()))

    mock_client = client_mock()
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

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = CollectionEpisode(())

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


async def test_badges_sensor_exposes_all_raw_fields_as_attributes(hass: HomeAssistant) -> None:
    """Expose every fetched badge's raw fields under the "badges" attribute."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    badge = Badge(
        id="1",
        code="debutant",
        name="Débutant",
        description="Vous avez regardé votre premier épisode.",
        date=datetime(2013, 8, 15, 10, 0, 0),  # noqa: DTZ001 (API doesn't return a timezone)
        height=256,
        width=256,
        level=None,
    )

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((badge,))
    mock_client.fetch_planning.return_value = CollectionEpisode(())

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_badges")
    assert state is not None
    assert state.state == "8"
    assert state.attributes["badges"] == [
        {
            "id": "1",
            "code": "debutant",
            "name": "Débutant",
            "description": "Vous avez regardé votre premier épisode.",
            "date": "2013-08-15T10:00:00",
            "height": 256,
            "width": 256,
            "level": None,
        }
    ]


async def test_other_sensors_have_no_extra_attributes(hass: HomeAssistant) -> None:
    """Report no extra_state_attributes for sensors with no attrs_fn (e.g. xp)."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge(())
    mock_client.fetch_planning.return_value = CollectionEpisode(())

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_xp")
    assert state is not None
    assert "badges" not in state.attributes


async def test_episode_sensors_expose_the_show_poster_as_entity_picture(hass: HomeAssistant) -> None:
    """Use the show's poster, resolved by the coordinator, as the sensor's picture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=USER_INPUT,
        options={CONF_PLANNING_MONTHS_BEHIND: 0},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.side_effect = [
        CollectionEpisode((_episode("1001", dt_util.now().date() - timedelta(days=1), seen=False),)),
        CollectionEpisode(()),
        CollectionEpisode(()),
    ]
    mock_client.fetch_shows.return_value = CollectionShow(
        {
            "55": Show(
                id="55",
                title="Example Show",
                additional_information=ShowAdditionalInformation(
                    original_title="Example Show",
                    imdb_id=None,
                    themoviedb_id=None,
                    genres=(),
                    showrunners=(),
                    aliases=(),
                    seasons=1,
                    followers=0,
                    network="Netflix",
                    country=None,
                    original_language=None,
                    length=30,
                    rating="",
                    notes_mean=0,
                    notes_total=0,
                    next_trailer=None,
                    resource_url="https://www.betaseries.com/serie/example-show",
                    images=ShowImages(
                        show=None,
                        banner="https://pictures.betaseries.com/banner.jpg",
                        box=None,
                        poster="https://pictures.betaseries.com/poster.jpg",
                        clearlogo="https://pictures.betaseries.com/logo.png",
                    ),
                ),
            )
        }
    )

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert state.attributes["entity_picture"] == "https://pictures.betaseries.com/poster.jpg"
    # The whole set is exposed too, so a card can pick another artwork than the
    # poster; kinds the show has no image for are absent rather than null.
    assert state.attributes["show_images"] == {
        "banner": "https://pictures.betaseries.com/banner.jpg",
        "poster": "https://pictures.betaseries.com/poster.jpg",
        "clearlogo": "https://pictures.betaseries.com/logo.png",
    }


async def test_episode_sensors_have_no_picture_without_a_poster(hass: HomeAssistant) -> None:
    """Expose no picture at all when the show has no poster.

    BetaSeries' episode thumbnail endpoint requires an API key, so it is not
    a usable fallback (see CLAUDE.md §4): no picture beats a broken image.
    """
    await _setup_with_planning(hass, (_episode("1001", dt_util.now().date() - timedelta(days=1), seen=False),))

    state = hass.states.get("sensor.betaseries_test_user_previous_episode_airing")
    assert state is not None
    assert "entity_picture" not in state.attributes
    assert state.attributes["show_images"] == {}


@pytest.mark.parametrize(
    ("entity_id", "attribute"),
    [
        ("sensor.betaseries_test_user_shows_to_catch_up_on", "shows"),
        ("sensor.betaseries_test_user_badges", "badges"),
        ("sensor.betaseries_test_user_previous_episode_airing", "show_images"),
    ],
)
async def test_bulky_attributes_are_kept_out_of_the_recorder(
    hass: HomeAssistant, entity_id: str, attribute: str
) -> None:
    """Keep the bulky attributes readable live, but out of the database.

    The recorder writes an entity's attributes alongside every state it
    stores, and drops all of them past MAX_STATE_ATTRS_BYTES (16 kB) - which
    the badge list and the watch list each approach on their own. Declaring
    them unrecorded costs nothing at runtime: cards, templates and automations
    still read them from the live state, which is what the first half of this
    test pins down.
    """
    today = dt_util.now().date()
    await _setup_with_planning(hass, (_episode("1001", today - timedelta(days=1), seen=False),))

    state = hass.states.get(entity_id)
    assert state is not None
    assert attribute in state.attributes

    # state_info is what the recorder itself reads off the State to build its
    # exclude set (see recorder/db_schema.py), so asserting on it checks the
    # same thing the database will.
    assert state.state_info is not None
    assert attribute in state.state_info["unrecorded_attributes"]
