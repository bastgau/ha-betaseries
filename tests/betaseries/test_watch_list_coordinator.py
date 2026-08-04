"""Tests for WatchListCoordinator and the watch_list sensor's list attribute."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_show import CollectionShow
from custom_components.betaseries.betaseries.collection_watch_list_show import CollectionWatchListShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.exceptions import Error
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.show_additional_information import ShowAdditionalInformation
from custom_components.betaseries.betaseries.show_images import ShowImages
from custom_components.betaseries.betaseries.watch_list_show import WatchListShow
from custom_components.betaseries.const import (
    CONF_EPISODES_LIMIT,
    CONF_EPISODES_SCAN_INTERVAL,
    CONF_SHOWS_LIMIT,
    DOMAIN,
)
from custom_components.betaseries.coordinator import WatchListCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET, STATE_UNAVAILABLE
from tests.conftest import client_mock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}
SAVED_DATA = {CONF_API_KEY: "test-api-key", "access_token": "token123"}

MEMBER_DATA = MemberData(
    identity=MemberIdentity(id="42", login="test_user"),
    stats=MemberStats(
        xp=1337,
        episodes_to_watch=726,
        time_to_spend=540,
        progress=77.4699,
        shows_to_watch=37,
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

EPISODE = Episode(
    id="3905073",
    season=2,
    number=1,
    code="S02E01",
    title="Urlaub",
    description="A thrilling episode summary.",
    air_date=date(2026, 5, 29),
    seen=False,
    platforms=("Netflix",),
    resource_url="https://www.betaseries.com/episode/3905073",
    show=Show(id="38605", title="Achtsam Morden"),
)

WATCH_LIST = CollectionWatchListShow(
    (
        WatchListShow(
            id="38605",
            title="Achtsam Morden",
            remaining=8,
            poster="https://pictures.betaseries.com/list-poster.jpg",
            episodes=CollectionEpisode((EPISODE,)),
        ),
    )
)

# The endpoint's own counters, returned alongside the (capped) collection.
WATCH_LIST_RESPONSE = (WATCH_LIST, 37, 726)


def _show_with_images(poster: str | None) -> Show:
    """Build a show carrying the additional information that holds its artwork."""
    return Show(
        id="38605",
        title="Achtsam Morden",
        additional_information=ShowAdditionalInformation(
            original_title="Achtsam Morden",
            imdb_id=None,
            themoviedb_id=None,
            genres=(),
            showrunners=(),
            aliases=(),
            seasons=2,
            followers=0,
            network="Netflix",
            country=None,
            original_language=None,
            length=30,
            rating="",
            notes_mean=0,
            notes_total=0,
            next_trailer=None,
            resource_url="https://www.betaseries.com/serie/achtsam-morden",
            images=ShowImages(show=None, banner=None, box=None, poster=poster, clearlogo=None),
        ),
    )


async def test_uses_default_scan_interval(hass: HomeAssistant) -> None:
    """Default to 30 minutes when no episodes_scan_interval option is set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)

    coordinator = WatchListCoordinator(hass, entry, client_mock())

    assert coordinator.update_interval == timedelta(minutes=30)


async def test_uses_configured_scan_interval(hass: HomeAssistant) -> None:
    """Use the episodes_scan_interval option when set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", options={CONF_EPISODES_SCAN_INTERVAL: 45})
    entry.add_to_hass(hass)

    coordinator = WatchListCoordinator(hass, entry, client_mock())

    assert coordinator.update_interval == timedelta(minutes=45)


async def test_sends_the_configured_limits(hass: HomeAssistant) -> None:
    """Pass the shows_limit/episodes_limit options through to the client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        options={CONF_SHOWS_LIMIT: 3.0, CONF_EPISODES_LIMIT: 2.0},
    )
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_watch_list.return_value = WATCH_LIST_RESPONSE

    coordinator = WatchListCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    # NumberSelector stores floats; the client must still receive ints.
    assert mock_client.fetch_watch_list.await_args.args == (3, 2)
    # No entity exposes the cast, so it is left out of the payload.
    assert mock_client.fetch_watch_list.await_args.kwargs == {"exclude_characters": True}
    assert coordinator.data.total_episodes == 726
    assert coordinator.data.total_shows == 37


async def test_show_images_failure_does_not_fail_the_refresh(hass: HomeAssistant) -> None:
    """Keep the watch list usable when only the artwork call fails."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    mock_client.fetch_watch_list.return_value = WATCH_LIST_RESPONSE
    mock_client.fetch_shows.side_effect = Error("shows endpoint is down")

    coordinator = WatchListCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    # Nothing is cached for the show: a failed call must not be remembered as
    # "this show has no artwork", or it would never be retried.
    assert coordinator.data.images == {}
    assert coordinator.data.total_episodes == 726
    assert coordinator.data.total_shows == 37


async def _setup(
    hass: HomeAssistant, watch_list: tuple[CollectionWatchListShow, int, int], shows: CollectionShow
) -> MockConfigEntry:
    """Set up an entry whose watch list and show artwork are mocked."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = CollectionEpisode(())
    mock_client.fetch_watch_list.return_value = watch_list
    mock_client.fetch_shows.return_value = shows

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_sensor_reports_the_totals_and_lists_the_shows(hass: HomeAssistant) -> None:
    """Expose the endpoint's own totals, and the (capped) list of shows."""
    await _setup(
        hass,
        WATCH_LIST_RESPONSE,
        CollectionShow({"38605": _show_with_images("https://pictures.betaseries.com/poster.jpg")}),
    )

    state = hass.states.get("sensor.betaseries_test_user_shows_to_catch_up_on")
    assert state is not None
    # The state is the show count, not the episode count, which episodes_to_watch
    # already reports from another endpoint. Both totals are the endpoint's own:
    # unaffected by the configured limits.
    assert state.state == "37"
    assert state.attributes["total_episodes"] == 726
    assert state.attributes["total_shows"] == 37

    shows = state.attributes["shows"]
    assert len(shows) == 1
    assert shows[0]["show_id"] == "38605"
    assert shows[0]["show_title"] == "Achtsam Morden"
    assert shows[0]["episode_remaining"] == 8
    assert shows[0]["show_images"] == {"poster": "https://pictures.betaseries.com/poster.jpg"}
    assert shows[0]["episodes"] == [
        {
            "id": "3905073",
            "code": "S02E01",
            "title": "Urlaub",
            "air_date": "2026-05-29",
            "platforms": ["Netflix"],
            "resource_url": "https://www.betaseries.com/episode/3905073",
        }
    ]


async def test_sensor_falls_back_to_the_poster_carried_by_the_list(hass: HomeAssistant) -> None:
    """Use the poster from /episodes/list when the artwork call brought nothing."""
    await _setup(hass, WATCH_LIST_RESPONSE, CollectionShow({"38605": _show_with_images(None)}))

    state = hass.states.get("sensor.betaseries_test_user_shows_to_catch_up_on")
    assert state is not None
    assert state.attributes["shows"][0]["show_images"] == {"poster": "https://pictures.betaseries.com/list-poster.jpg"}


async def test_sensor_is_unavailable_when_the_watch_list_failed(hass: HomeAssistant) -> None:
    """Report unavailable, rather than a misleading zero, when the watch list could not be fetched.

    The entity is backed solely by the watch list, so an outage there leaves
    it with nothing to show - unlike the plain statistics sensors, which keep
    working from the member data.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_planning.return_value = CollectionEpisode(())
    mock_client.fetch_watch_list.side_effect = Error("watch list is down")

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.betaseries_test_user_shows_to_catch_up_on")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # The statistics sensors are untouched: they come from the member data.
    episodes_state = hass.states.get("sensor.betaseries_test_user_episodes_to_watch")
    assert episodes_state is not None
    assert episodes_state.state == "726"
    shows_state = hass.states.get("sensor.betaseries_test_user_shows_not_started")
    assert shows_state is not None
    assert shows_state.state == "37"

    # Its own properties still answer, so nothing crashes while HA adds it.
    entity = hass.data["entity_components"]["sensor"].get_entity("sensor.betaseries_test_user_shows_to_catch_up_on")
    assert entity is not None
    assert entity.extra_state_attributes == {"total_shows": 0, "total_episodes": 0, "shows": []}
