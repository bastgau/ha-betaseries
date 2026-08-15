"""Tests for the BetaSeries services (see CLAUDE.md §8)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.exceptions import AuthError, Error, NotWatchedError
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.show_additional_information import ShowAdditionalInformation
from custom_components.betaseries.betaseries.show_images import ShowImages
from custom_components.betaseries.const import DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from tests.conftest import client_mock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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


SEARCH_RESULT = Show(
    id="38605",
    title="Achtsam Morden",
    description="Un avocat véreux devient tueur à gages malgré lui.",
    slug="achtsam-morden",
    additional_information=ShowAdditionalInformation(
        original_title="Achtsam Morden",
        imdb_id="tt30217222",
        themoviedb_id="252372",
        genres=("Comédie", "Crime"),
        showrunners=("Karsten Dusse",),
        aliases=(),
        seasons=2,
        followers=5974,
        network="Netflix",
        country="Allemagne",
        original_language="allemand",
        length=30,
        rating="",
        notes_mean=3.89,
        notes_total=164,
        trailer_url=None,
        resource_url="https://www.betaseries.com/serie/achtsam-morden",
        images=ShowImages(
            show="https://pictures.betaseries.com/fonds/show/a.jpg",
            banner=None,
            box=None,
            poster="https://pictures.betaseries.com/fonds/poster/a.jpg",
            clearlogo=None,
        ),
        creation="2024",
        broadcast_status="Continuing",
        platforms=("Netflix", "Apple TV+"),
        in_account=False,
    ),
)


async def _async_setup(hass: HomeAssistant, mock_client: AsyncMock) -> MockConfigEntry:
    """Set up a BetaSeries entry backed by the given mocked client."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _client_mock() -> AsyncMock:
    """Build a client mock with the defaults every service test needs for setup to succeed."""
    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges
    mock_client.fetch_planning.return_value = ()
    return mock_client


@pytest.mark.parametrize(
    ("service", "data", "method", "call_args"),
    [
        (
            "mark_episode_watched",
            {"episode_id": "3905073,3685365"},
            "mark_episodes_watched",
            (["3905073", "3685365"],),
        ),
        ("mark_episode_unwatched", {"episode_id": "3905073"}, "mark_episodes_unwatched", (["3905073"],)),
        ("rate_episode", {"episode_id": "3905073", "note": 4}, "rate_episodes", (["3905073"], 4)),
        ("unrate_episode", {"episode_id": "3905073"}, "unrate_episodes", (["3905073"],)),
        ("mark_season_watched", {"show_id": "38605", "season": 2}, "mark_season_watched", ("38605", 2)),
        ("mark_season_unwatched", {"show_id": "38605", "season": 2}, "mark_season_unwatched", ("38605", 2)),
        ("rate_season", {"show_id": "38605", "season": 2, "note": 4}, "rate_season", ("38605", 2, 4)),
        ("unrate_season", {"show_id": "38605", "season": 2}, "unrate_season", ("38605", 2)),
        ("rate_show", {"show_id": "38605", "note": 4}, "rate_show", ("38605", 4)),
        ("unrate_show", {"show_id": "38605"}, "unrate_show", ("38605",)),
        ("add_show", {"show_id": "38605"}, "add_show", ("38605",)),
        ("delete_token", {}, "delete_token", ()),
    ],
)
async def test_service_calls_the_matching_client_method(
    hass: HomeAssistant, service: str, data: dict[str, object], method: str, call_args: tuple[object, ...]
) -> None:
    """Route each service call to its matching Client method, with the right arguments."""
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)

    await hass.services.async_call(DOMAIN, service, {"config_entry": entry.entry_id, **data}, blocking=True)

    getattr(mock_client, method).assert_awaited_once_with(*call_args)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("mark_episode_watched", {"episode_id": "3905073"}),
        ("mark_episode_unwatched", {"episode_id": "3905073"}),
        ("mark_season_watched", {"show_id": "38605", "season": 2}),
        ("mark_season_unwatched", {"show_id": "38605", "season": 2}),
    ],
)
async def test_watched_services_refresh_member_and_watch_list(
    hass: HomeAssistant, service: str, data: dict[str, object]
) -> None:
    """Refresh both MemberCoordinator and WatchListCoordinator after a successful watched-status change.

    These are the two coordinators backing the entities such an action can
    actually move (episodes_to_watch, shows_to_catch_up_on/suggestion) - see
    CLAUDE.md §8.
    """
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)
    fetch_calls_before = mock_client.fetch_member_data.await_count
    watch_list_calls_before = mock_client.fetch_watch_list.await_count

    await hass.services.async_call(DOMAIN, service, {"config_entry": entry.entry_id, **data}, blocking=True)

    assert mock_client.fetch_member_data.await_count > fetch_calls_before
    assert mock_client.fetch_watch_list.await_count > watch_list_calls_before


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("rate_episode", {"episode_id": "3905073", "note": 4}),
        ("unrate_episode", {"episode_id": "3905073"}),
        ("rate_season", {"show_id": "38605", "season": 2, "note": 4}),
        ("unrate_season", {"show_id": "38605", "season": 2}),
        ("rate_show", {"show_id": "38605", "note": 4}),
        ("unrate_show", {"show_id": "38605"}),
    ],
)
async def test_rating_services_do_not_refresh_any_coordinator(
    hass: HomeAssistant, service: str, data: dict[str, object]
) -> None:
    """Skip refreshing after a rating action: no entity displays a member's own rating (CLAUDE.md §8)."""
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)
    fetch_calls_before = mock_client.fetch_member_data.await_count
    watch_list_calls_before = mock_client.fetch_watch_list.await_count

    await hass.services.async_call(DOMAIN, service, {"config_entry": entry.entry_id, **data}, blocking=True)

    assert mock_client.fetch_member_data.await_count == fetch_calls_before
    assert mock_client.fetch_watch_list.await_count == watch_list_calls_before


async def test_delete_token_refreshes_member_but_not_watch_list(hass: HomeAssistant) -> None:
    """Refresh MemberCoordinator only: it is what surfaces the reauth prompt, watch_list has no auth of its own."""
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)
    fetch_calls_before = mock_client.fetch_member_data.await_count
    watch_list_calls_before = mock_client.fetch_watch_list.await_count

    await hass.services.async_call(DOMAIN, "delete_token", {"config_entry": entry.entry_id}, blocking=True)

    assert mock_client.fetch_member_data.await_count > fetch_calls_before
    assert mock_client.fetch_watch_list.await_count == watch_list_calls_before


@pytest.mark.parametrize(
    ("service", "data", "method"),
    [
        ("mark_episode_watched", {"episode_id": "3905073"}, "mark_episodes_watched"),
        ("mark_episode_unwatched", {"episode_id": "3905073"}, "mark_episodes_unwatched"),
        ("rate_episode", {"episode_id": "3905073", "note": 4}, "rate_episodes"),
        ("unrate_episode", {"episode_id": "3905073"}, "unrate_episodes"),
        ("mark_season_watched", {"show_id": "38605", "season": 2}, "mark_season_watched"),
        ("mark_season_unwatched", {"show_id": "38605", "season": 2}, "mark_season_unwatched"),
        ("rate_season", {"show_id": "38605", "season": 2, "note": 4}, "rate_season"),
        ("unrate_season", {"show_id": "38605", "season": 2}, "unrate_season"),
        ("rate_show", {"show_id": "38605", "note": 4}, "rate_show"),
        ("unrate_show", {"show_id": "38605"}, "unrate_show"),
        ("add_show", {"show_id": "38605"}, "add_show"),
        ("delete_token", {}, "delete_token"),
    ],
)
async def test_each_service_surfaces_a_client_error(
    hass: HomeAssistant, service: str, data: dict[str, object], method: str
) -> None:
    """Raise a HomeAssistantError when the underlying client call fails, for every service."""
    mock_client = _client_mock()
    getattr(mock_client, method).side_effect = Error("boom", status=500, body="{}")
    entry = await _async_setup(hass, mock_client)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, service, {"config_entry": entry.entry_id, **data}, blocking=True)


async def test_episode_id_trims_whitespace_around_commas(hass: HomeAssistant) -> None:
    """Split ATTR_EPISODE_ID on commas and trim whitespace, not just a bare split.

    A plain text field (not HA's "multiple" text selector, which loses input
    focus on every keystroke in the Developer Tools > Actions form - see
    services.py's _episode_ids docstring), so a user may reasonably type
    "1001, 1002" with a space after the comma.
    """
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)

    await hass.services.async_call(
        DOMAIN,
        "mark_episode_watched",
        {"config_entry": entry.entry_id, "episode_id": " 3905073 , 3685365 "},
        blocking=True,
    )

    mock_client.mark_episodes_watched.assert_awaited_once_with(["3905073", "3685365"])


async def test_not_watched_error_raises_service_validation_error(hass: HomeAssistant) -> None:
    """Surface NotWatchedError as a ServiceValidationError, not a generic HomeAssistantError."""
    mock_client = _client_mock()
    mock_client.rate_episodes.side_effect = NotWatchedError("not watched", status=400, body="{}")
    entry = await _async_setup(hass, mock_client)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "rate_episode",
            {"config_entry": entry.entry_id, "episode_id": "3905073", "note": 4},
            blocking=True,
        )


async def test_auth_error_raises_home_assistant_error(hass: HomeAssistant) -> None:
    """Surface AuthError as a HomeAssistantError - the entry's own reauth flow handles it separately."""
    mock_client = _client_mock()
    mock_client.rate_show.side_effect = AuthError("rejected", status=400, body="{}")
    entry = await _async_setup(hass, mock_client)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, "rate_show", {"config_entry": entry.entry_id, "show_id": "38605", "note": 4}, blocking=True
        )
    assert not isinstance(exc_info.value, ServiceValidationError)


async def test_add_show_refreshes_member_and_watch_list(hass: HomeAssistant) -> None:
    """Refresh both coordinators after adding a show: it moves the account's counters and the catch-up list."""
    mock_client = _client_mock()
    entry = await _async_setup(hass, mock_client)
    fetch_calls_before = mock_client.fetch_member_data.await_count
    watch_list_calls_before = mock_client.fetch_watch_list.await_count

    await hass.services.async_call(
        DOMAIN, "add_show", {"config_entry": entry.entry_id, "show_id": "38605"}, blocking=True
    )

    assert mock_client.fetch_member_data.await_count > fetch_calls_before
    assert mock_client.fetch_watch_list.await_count > watch_list_calls_before


async def test_search_shows_returns_the_matching_shows(hass: HomeAssistant) -> None:
    """Return one flat dict per result, holding what a card or a template can act on."""
    mock_client = _client_mock()
    mock_client.search_shows.return_value = (SEARCH_RESULT,)
    entry = await _async_setup(hass, mock_client)

    response = await hass.services.async_call(
        DOMAIN,
        "search_shows",
        {"config_entry": entry.entry_id, "query": "achtsam"},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "shows": [
            {
                "id": "38605",
                "title": "Achtsam Morden",
                "year": "2024",
                "status": "Continuing",
                "rating": 3.89,
                "platforms": ["Netflix", "Apple TV+"],
                "genres": ["Comédie", "Crime"],
                "seasons": 2,
                "followers": 5974,
                "in_account": False,
                "poster": "https://pictures.betaseries.com/fonds/poster/a.jpg",
                "fanart": "https://pictures.betaseries.com/fonds/show/a.jpg",
                "summary": "Un avocat véreux devient tueur à gages malgré lui.",
                "resource_url": "https://www.betaseries.com/serie/achtsam-morden",
            }
        ]
    }


async def test_search_shows_returns_an_empty_list_when_nothing_matches(hass: HomeAssistant) -> None:
    """Answer with an empty list rather than no response at all, so a caller can tell the two apart."""
    mock_client = _client_mock()
    mock_client.search_shows.return_value = ()
    entry = await _async_setup(hass, mock_client)

    response = await hass.services.async_call(
        DOMAIN,
        "search_shows",
        {"config_entry": entry.entry_id, "query": "nothing at all"},
        blocking=True,
        return_response=True,
    )

    assert response == {"shows": []}


async def test_search_shows_falls_back_to_the_slug_derived_url(hass: HomeAssistant) -> None:
    """Use Show.resource_url when the payload carried none, and tolerate absent details."""
    mock_client = _client_mock()
    mock_client.search_shows.return_value = (Show(id="1", title="Bare", slug="bare"),)
    entry = await _async_setup(hass, mock_client)

    response = await hass.services.async_call(
        DOMAIN,
        "search_shows",
        {"config_entry": entry.entry_id, "query": "bare"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    show = cast("list[dict[str, object]]", response["shows"])[0]
    assert show["resource_url"] == "https://www.betaseries.com/serie/bare"
    assert show["year"] is None
    assert show["platforms"] == []
    assert show["in_account"] is False


@pytest.mark.parametrize(("data", "expected_limit"), [({}, 20), ({"limit": 5}, 5)])
async def test_search_shows_passes_the_limit(hass: HomeAssistant, data: dict[str, object], expected_limit: int) -> None:
    """Send the requested result count, defaulting to 20 when the caller omits it."""
    mock_client = _client_mock()
    mock_client.search_shows.return_value = ()
    entry = await _async_setup(hass, mock_client)

    await hass.services.async_call(
        DOMAIN,
        "search_shows",
        {"config_entry": entry.entry_id, "query": "achtsam", **data},
        blocking=True,
        return_response=True,
    )

    mock_client.search_shows.assert_awaited_once_with("achtsam", limit=expected_limit)


async def test_search_shows_does_not_refresh_any_coordinator(hass: HomeAssistant) -> None:
    """Change nothing: a search is a read, and refreshing on every keystroke would hammer the API."""
    mock_client = _client_mock()
    mock_client.search_shows.return_value = ()
    entry = await _async_setup(hass, mock_client)
    fetch_calls_before = mock_client.fetch_member_data.await_count
    watch_list_calls_before = mock_client.fetch_watch_list.await_count

    await hass.services.async_call(
        DOMAIN,
        "search_shows",
        {"config_entry": entry.entry_id, "query": "achtsam"},
        blocking=True,
        return_response=True,
    )

    assert mock_client.fetch_member_data.await_count == fetch_calls_before
    assert mock_client.fetch_watch_list.await_count == watch_list_calls_before


async def test_search_shows_surfaces_a_client_error(hass: HomeAssistant) -> None:
    """Raise a HomeAssistantError when the search request fails."""
    mock_client = _client_mock()
    mock_client.search_shows.side_effect = Error("boom", status=500, body="{}")
    entry = await _async_setup(hass, mock_client)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "search_shows",
            {"config_entry": entry.entry_id, "query": "achtsam"},
            blocking=True,
            return_response=True,
        )


async def test_generic_error_raises_home_assistant_error(hass: HomeAssistant) -> None:
    """Surface any other client Error as a generic HomeAssistantError."""
    mock_client = _client_mock()
    mock_client.rate_show.side_effect = Error("boom", status=500, body="{}")
    entry = await _async_setup(hass, mock_client)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "rate_show", {"config_entry": entry.entry_id, "show_id": "38605", "note": 4}, blocking=True
        )
