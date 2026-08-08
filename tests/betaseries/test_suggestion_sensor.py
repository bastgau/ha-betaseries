"""Tests for the "Suggestion of the day" sensor.

Most of these drive `_suggestion_of_the_day` directly rather than through Home
Assistant: what has to be pinned down is not that an episode comes out, but
*which* one and when it is allowed to change - and that is a property of the
picking function, exercised far more cheaply and far more precisely on its own.

Worth stating plainly, because the coverage report will not: before this file
existed the sensor sat at 100% line and branch coverage with nothing asserting
a single one of its behaviours. Setting the integration up runs the picker, so
the lines were reached; none of the contract below was verified.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import patch

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_watch_list_show import CollectionWatchListShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.watch_list_show import WatchListShow
from custom_components.betaseries.const import CONF_UPCOMING_MEDIA_CARD, DOMAIN
from custom_components.betaseries.coordinator import WatchListData
from custom_components.betaseries.sensor import (
    _suggestion_of_the_day,  # pyright: ignore[reportPrivateUsage]
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from tests.conftest import client_mock

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

ENTITY_ID = "sensor.betaseries_test_user_suggestion_of_the_day"

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


def _episode(episode_id: str, *, season: int = 1, number: int = 1, title: str | None = None) -> Episode:
    """Build one unseen episode."""
    return Episode(
        id=episode_id,
        season=season,
        number=number,
        code=f"S{season:02d}E{number:02d}",
        title=f"Episode {episode_id}" if title is None else title,
        description="",
        air_date=date(2026, 7, 1),
        seen=False,
        platforms=("Netflix",),
        resource_url=f"https://www.betaseries.com/episode/{episode_id}",
        show=Show(id="unused", title="unused"),
    )


def _show(show_id: str, *, episodes: tuple[Episode, ...] = (), remaining: int = 5) -> WatchListShow:
    """Build one show of the watch list."""
    return WatchListShow(
        id=show_id,
        title=f"Show {show_id}",
        remaining=remaining,
        poster=f"https://pictures.betaseries.com/{show_id}.jpg",
        episodes=CollectionEpisode(episodes or (_episode(f"{show_id}01"),)),
    )


def _data(*shows: WatchListShow, images: dict[str, dict[str, str]] | None = None) -> WatchListData:
    """Build the watch list a refresh would have produced."""
    return WatchListData(
        shows=CollectionWatchListShow(shows),
        total_shows=len(shows),
        total_episodes=sum(len(show.episodes) for show in shows),
        images=images or {},
        ratings={},
        trailers={},
        genres={},
    )


TEN_SHOWS = tuple(_show(str(show_id)) for show_id in range(10, 20))


def test_pick_is_stable_within_the_same_day(freezer: FrozenDateTimeFactory) -> None:
    """Return the same episode every time it is asked on a given day.

    This is what makes the sensor a sensor: its state has to be reproducible
    from the data it was built on, across refreshes and across restarts. There
    is no stored pick to consult - the answer is recomputed from scratch every
    time and lands on the same show because its two inputs have not moved.
    """
    freezer.move_to("2026-08-02 09:00:00")
    data = _data(*TEN_SHOWS)

    first = _suggestion_of_the_day(data)
    freezer.move_to("2026-08-02 23:30:00")
    second = _suggestion_of_the_day(data)

    assert first is not None
    assert second == first


def test_pick_rotates_from_one_day_to_the_next(freezer: FrozenDateTimeFactory) -> None:
    """Suggest something else as the days go by, which is the point of the feature."""
    data = _data(*TEN_SHOWS)
    picked: list[str] = []
    for day in range(1, 15):
        freezer.move_to(f"2026-08-{day:02d}")
        pick = _suggestion_of_the_day(data)
        assert pick is not None
        picked.append(pick[0].id)

    # Not asserting every day differs - two consecutive days landing on the
    # same show is legitimate - but a fortnight stuck on one show would mean
    # the day is not reaching the score at all.
    assert len(set(picked)) > 1


def test_pick_survives_another_show_leaving_the_list(freezer: FrozenDateTimeFactory) -> None:
    """Keep the same suggestion when an unrelated show drops out of the watch list.

    The reason the pick is a per-show score rather than a draw. `random.choice`
    resolves to `int(random() * len(seq))`, so removing *any* element shifts
    every index and reshuffles the answer - finishing a show you were not being
    suggested would silently change tonight's suggestion. Scoring each show on
    its own makes removals affect nothing but the removed show.
    """
    freezer.move_to("2026-08-02")
    pick = _suggestion_of_the_day(_data(*TEN_SHOWS))
    assert pick is not None
    chosen = pick[0].id

    # Every other show finishes, one at a time; the winner must not move.
    for show in TEN_SHOWS:
        if show.id == chosen:
            continue
        reduced = _data(*(other for other in TEN_SHOWS if other.id != show.id))
        still = _suggestion_of_the_day(reduced)
        assert still is not None
        assert still[0].id == chosen, f"removing show {show.id} moved the suggestion"


def test_pick_moves_on_when_the_chosen_show_leaves(freezer: FrozenDateTimeFactory) -> None:
    """Suggest another show once the chosen one has nothing left to watch."""
    freezer.move_to("2026-08-02")
    pick = _suggestion_of_the_day(_data(*TEN_SHOWS))
    assert pick is not None
    chosen = pick[0].id

    remaining = _data(*(show for show in TEN_SHOWS if show.id != chosen))
    replacement = _suggestion_of_the_day(remaining)

    assert replacement is not None
    assert replacement[0].id != chosen


def test_watching_the_suggested_episode_hands_the_day_to_another_show(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Move on once the suggested episode has been watched, without storing anything.

    This is what separates a suggestion from a playlist, and it is why the
    episode's id is part of the score and not just the show's: watching it
    changes which episode that show is resumed at, so the show's score changes
    and it usually loses the day.

    Asserted as a rate rather than a certainty because it genuinely is one -
    the show can win again with its next episode, at roughly one chance in the
    number of shows listed. Measured at ~82% over 10 shows and ~95% over 38, so
    a 60% floor here fails loudly if the episode ever stops feeding the score,
    while never flaking on the legitimate case.
    """
    moved = 0
    days = 60
    for day in range(days):
        freezer.move_to("2026-08-02 12:00:00")
        freezer.tick(86400 * day)
        pick = _suggestion_of_the_day(_data(*TEN_SHOWS))
        assert pick is not None
        chosen, watched = pick

        # The member watches it: that show is now resumed one episode later.
        after = _data(
            *(
                _show(show.id, episodes=(_episode(f"{show.id}02", number=2),)) if show.id == chosen.id else show
                for show in TEN_SHOWS
            )
        )
        following = _suggestion_of_the_day(after)
        assert following is not None
        assert following[1].id != watched.id, "the watched episode is still being suggested"
        moved += following[0].id != chosen.id

    assert moved / days > 0.6, f"the suggestion only left the watched show {moved}/{days} times"


def test_pick_resumes_at_the_oldest_unseen_episode(freezer: FrozenDateTimeFactory) -> None:
    """Point at the episode the member stopped on, not the newest one.

    A series is picked up where it was left off, so the pick has to be the
    first of the show's unseen episodes - the endpoint returns them oldest
    first. Suggesting any other one would offer S01E03 to someone who stopped
    after S01E01.
    """
    freezer.move_to("2026-08-02")
    oldest = _episode("7001", number=1)
    newer = _episode("7002", number=2)
    data = _data(_show("70", episodes=(oldest, newer)))

    pick = _suggestion_of_the_day(data)

    assert pick is not None
    assert pick[1] == oldest


def test_no_suggestion_when_the_watch_list_is_empty(freezer: FrozenDateTimeFactory) -> None:
    """Suggest nothing when there is nothing left to watch."""
    freezer.move_to("2026-08-02")

    assert _suggestion_of_the_day(_data()) is None


def test_a_show_with_no_listed_episode_is_not_suggested(freezer: FrozenDateTimeFactory) -> None:
    """Skip a show whose episodes are all missing from the payload.

    `episodes_limit` caps how many episodes each show carries, and a show can
    come back with none at all. It cannot be resumed, so suggesting it would
    name a show with no episode to go with it.
    """
    freezer.move_to("2026-08-02")
    empty = WatchListShow(id="99", title="Show 99", remaining=3, poster=None, episodes=CollectionEpisode(()))
    data = _data(empty, _show("70"))

    pick = _suggestion_of_the_day(data)

    assert pick is not None
    assert pick[0].id == "70"


async def _setup_with_watch_list(
    hass: HomeAssistant, *shows: WatchListShow, options: dict[str, object] | None = None
) -> MockConfigEntry:
    """Set up an entry whose watch list holds the given shows."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT, options=options or {})
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_watch_list.return_value = (
        CollectionWatchListShow(shows),
        len(shows),
        sum(len(show.episodes) for show in shows),
    )

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_sensor_exposes_the_suggestion(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Expose the episode as the state, with its identifiers in the attributes."""
    freezer.move_to("2026-08-02")
    await _setup_with_watch_list(hass, _show("70", episodes=(_episode("7001", season=2, number=3, title="Urlaub"),)))

    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "Show 70 S02E03 : Urlaub"
    assert state.attributes["show_id"] == "70"
    assert state.attributes["episode_id"] == "7001"
    assert state.attributes["code"] == "S02E03"
    assert state.attributes["episode_remaining"] == 5


async def test_sensor_data_attribute_is_absent_by_default(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Leave the upcoming-media-card `data` attribute out unless the option is turned on."""
    freezer.move_to("2026-08-02")
    await _setup_with_watch_list(hass, _show("70", episodes=(_episode("7001", season=2, number=3, title="Urlaub"),)))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert "data" not in state.attributes


async def test_sensor_data_attribute_shapes_the_single_suggestion(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Expose today's suggestion as a single-item upcoming-media-card `data` list.

    Same contract as the other `data` shapes on this integration (verified
    against the card's source): element 0 is a template object, never a media
    item - here followed by exactly one episode, since this sensor only ever
    suggests one. `flag` is always true: the suggestion is always unwatched.
    """
    freezer.move_to("2026-08-02")
    await _setup_with_watch_list(
        hass,
        _show("70", episodes=(_episode("7001", season=2, number=3, title="Urlaub"),)),
        options={CONF_UPCOMING_MEDIA_CARD: True},
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    data = state.attributes["data"]

    assert data[0] == {
        "title_default": "$title",
        "line1_default": "$episode",
        "line2_default": "$number",
        "line3_default": "$date",
        "line4_default": "$empty",
        "icon": "mdi:television-classic",
    }
    assert len(data) == 2
    assert data[1] == {
        "airdate": "2026-07-01",
        "title": "Show 70",
        "episode": "Urlaub",
        "number": "S02E03",
        "poster": "https://pictures.betaseries.com/70.jpg",
        "fanart": None,
        "deep_link": "https://www.betaseries.com/episode/7001",
        "summary": "",
        "rating": None,
        "studio": "Netflix",
        "genres": None,
        "trailer": None,
        "flag": True,
    }


async def test_sensor_drops_the_separator_without_an_episode_title(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Leave no dangling " : " when BetaSeries has no title for the episode."""
    freezer.move_to("2026-08-02")
    await _setup_with_watch_list(hass, _show("70", episodes=(_episode("7001", season=2, number=3, title=""),)))

    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "Show 70 S02E03"


async def test_sensor_is_unknown_with_nothing_to_watch(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Report an unknown state, with no attributes, when the watch list is empty."""
    freezer.move_to("2026-08-02")
    await _setup_with_watch_list(hass)

    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "unknown"
    assert "episode_id" not in state.attributes
