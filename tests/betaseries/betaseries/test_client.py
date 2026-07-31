"""Tests for Client (authenticated data endpoints).

See test_auth.py for why aiohttp.ClientSession is mocked by hand instead of
using aioresponses.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import aiohttp
from custom_components.betaseries.betaseries.client import Client
from custom_components.betaseries.betaseries.episode_watched_event import EpisodeWatchedEvent
from custom_components.betaseries.betaseries.exceptions import AuthError, Error
from custom_components.betaseries.betaseries.season_watched_event import SeasonWatchedEvent
from custom_components.betaseries.betaseries.timeline_event_type import TimelineEventType
import pytest

from .test_auth import FakeResponse, FakeSession

API_KEY = "test-api-key"
ACCESS_TOKEN = "token123"

MEMBER_PAYLOAD = {
    "member": {
        "id": 42,
        "login": "test_user",
        "xp": 1337,
        "stats": {
            "episodes_to_watch": 12,
            "time_to_spend": 540,
            "progress": 77.4699,
            "shows_to_watch": 3,
            "movies_to_watch": 2,
            "shows_current": 5,
            "badges": 8,
            "shows": 40,
            "shows_finished": 30,
            "episodes": 1200,
            "time_on_tv": 54000,
            "movies": 100,
            "streak_days": 15,
            "member_since_days": 3650,
            "episodes_per_month": 25.5,
            "favorite_genre": "Drama",
        },
    }
}


async def test_fetch_member_data_success() -> None:
    """Return a MemberData built from the JSON payload on HTTP 200."""
    session = FakeSession(get_responses=[FakeResponse(200, MEMBER_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_member_data()

    assert result.identity.id == "42"
    assert result.identity.login == "test_user"
    assert result.stats.xp == 1337
    assert result.stats.episodes_to_watch == 12
    assert result.stats.time_to_spend == 540
    assert result.stats.progress == 77.4699
    assert result.stats.shows_to_watch == 3
    assert result.stats.movies_to_watch == 2
    assert result.stats.shows_current == 5
    assert result.stats.badges == 8
    assert result.stats.shows == 40
    assert result.stats.shows_finished == 30
    assert result.stats.episodes == 1200
    assert result.stats.time_on_tv == 54000
    assert result.stats.movies == 100
    assert result.stats.streak_days == 15
    assert result.stats.member_since_days == 3650
    assert result.stats.episodes_per_month == 25.5
    assert result.stats.favorite_genre == "Drama"


async def test_fetch_member_data_sends_default_locale_param() -> None:
    """Default to "locale": "fr" when no locale is given, matching BetaSeries' own default."""
    session = FakeSession(get_responses=[FakeResponse(200, MEMBER_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_member_data()

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr"}


async def test_fetch_member_data_sends_configured_locale_param() -> None:
    """Send the "locale" query param the client was configured with."""
    session = FakeSession(get_responses=[FakeResponse(200, MEMBER_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN, "en")  # type: ignore[arg-type]

    await client.fetch_member_data()

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "en"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_member_data_failure(status: int) -> None:
    """Raise Error, carrying the response's status/body, when fetching member data fails.

    The client itself never logs this - it attaches the response to the
    exception so the caller (e.g. Home Assistant's coordinator) can.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status, {"errors": [{"code": 9999, "text": "boom"}]})])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error) as exc_info:
        await client.fetch_member_data()

    assert exc_info.value.status == status
    assert exc_info.value.body is not None
    assert "boom" in exc_info.value.body


@pytest.mark.parametrize(
    ("code", "text"),
    [
        (1001, "Mauvaise clé API."),
        (2001, "Données d'identification incorrectes."),
    ],
)
async def test_fetch_member_data_raises_auth_error_on_invalid_credentials(code: int, text: str) -> None:
    """Raise AuthError on HTTP 400 with either of BetaSeries' "invalid credentials" error codes.

    Both verified in production on this endpoint (HTTP 400, not 401):
    1001 for a rejected api_key (X-BetaSeries-Key), 2001 for a rejected
    access token - the latter is the same numeric code as the unrelated
    device-flow "pending" state (see const.ERROR_CODE_PENDING).

    Args:
        code (int): The BetaSeries error code returned in the response body.
        text (str): The corresponding localized error text (unused by the client).

    """
    payload = {"errors": [{"code": code, "text": text}]}
    session = FakeSession(get_responses=[FakeResponse(400, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(AuthError) as exc_info:
        await client.fetch_member_data()

    assert exc_info.value.status == 400
    assert exc_info.value.body is not None
    assert str(code) in exc_info.value.body


PLANNING_PAYLOAD = {
    "episodes": [
        {
            "id": 1001,
            "season": 3,
            "episode": 4,
            "code": "S03E04",
            "title": "The One With The Tests",
            "description": "A thrilling episode summary.",
            "date": "2026-08-01",
            "user": {"seen": False},
            "show": {"id": 55, "title": "Example Show", "description": "A show about tests.", "slug": "example-show"},
            "platform_links": [{"platform": "Netflix"}, {"platform": "Apple TV"}],
            "resource_url": "https://www.betaseries.com/episode/1001",
        }
    ]
}


async def test_fetch_planning_success() -> None:
    """Return a CollectionEpisode built from the JSON payload on HTTP 200."""
    session = FakeSession(get_responses=[FakeResponse(200, PLANNING_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_planning("2026-08")

    assert len(result) == 1
    episode = next(iter(result))
    show = episode.show
    assert episode.id == "1001"
    assert show.id == "55"
    assert show.title == "Example Show"
    assert show.description == "A show about tests."
    assert show.slug == "example-show"
    assert show.resource_url == "https://www.betaseries.com/serie/example-show"
    assert episode.season == 3
    assert episode.number == 4
    assert episode.code == "S03E04"
    assert episode.title == "The One With The Tests"
    assert episode.description == "A thrilling episode summary."
    assert episode.air_date == date(2026, 8, 1)
    assert episode.seen is False
    assert episode.platforms == ("Netflix", "Apple TV")
    assert episode.resource_url == "https://www.betaseries.com/episode/1001"


async def test_fetch_planning_keeps_empty_description_as_is() -> None:
    """Leave the episode's description empty as-is, with no fallback to the show's.

    Not every source of Episode has a show with a description (e.g. GET
    /shows/episodes' show sub-object doesn't) - so this is left to consumers
    to handle, not assumed by the client.
    """
    payload = {
        "episodes": [
            {
                **PLANNING_PAYLOAD["episodes"][0],
                "description": "",
            }
        ]
    }
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_planning("2026-08")

    assert next(iter(result)).description == ""


async def test_fetch_planning_sends_month_param() -> None:
    """Send the requested month as a query param.

    "month" is verified (via Bruno) to filter strictly server-side on
    GET /planning/member, unlike "fields" which that endpoint ignores.
    Unlike "unseen", it is not passed, so both seen and unseen episodes
    are returned - filtering by seen is done client-side (calendar.py,
    sensor.py) so the calendar can show past/watched episodes too.
    """
    session = FakeSession(get_responses=[FakeResponse(200, PLANNING_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_planning("2026-08")

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "month": "2026-08"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_planning_failure(status: int) -> None:
    """Raise Error when fetching the planning fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_planning("2026-08")


async def test_fetch_planning_raises_auth_error_on_invalid_credentials() -> None:
    """Raise AuthError on HTTP 400 with BetaSeries' "invalid credentials" error code."""
    payload = {"errors": [{"code": 2001, "text": "Données d'identification incorrectes."}]}
    session = FakeSession(get_responses=[FakeResponse(400, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await client.fetch_planning("2026-08")


SHOW_EPISODES_PAYLOAD: dict[str, Any] = {
    "episodes": [
        {
            "id": 303877,
            "title": "Cool Your Jets",
            "season": 1,
            "episode": 1,
            "code": "S01E01",
            "description": "The Honor crew welcomes their first group of charter guests.",
            "date": "2013-07-02",
            "user": {"seen": False},
            "show": {"id": 6947, "thetvdb_id": 270205, "title": "Below Deck", "in_account": True},
            "platform_links": [{"platform": "M6+"}],
            "resource_url": "https://www.betaseries.com/episode/below-deck/s01e01",
        },
        {
            "id": 303878,
            "title": "Anchors Aweigh",
            "season": 1,
            "episode": 2,
            "code": "S01E02",
            "description": "",
            "date": "2013-07-09",
            "user": {"seen": True},
            "show": {"id": 6947, "thetvdb_id": 270205, "title": "Below Deck", "in_account": True},
            "platform_links": [],
            "resource_url": "https://www.betaseries.com/episode/below-deck/s01e02",
        },
    ],
    "errors": [],
}


async def test_fetch_show_episodes_success() -> None:
    """Return a CollectionEpisode built from the JSON payload on HTTP 200.

    Uses a /shows/episodes-shaped show sub-object (id, thetvdb_id, title,
    in_account - no description, unlike /planning/member's), verified via
    Bruno (bruno/Shows/show-episodes.bru) to confirm _parse_episode handles it.
    """
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_EPISODES_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_show_episodes("6947")

    assert len(result) == 2
    first, second = tuple(result)
    assert first.id == "303877"
    assert first.title == "Cool Your Jets"
    assert first.season == 1
    assert first.number == 1
    assert first.code == "S01E01"
    assert first.seen is False
    assert first.show.id == "6947"
    assert first.show.title == "Below Deck"
    assert first.show.description is None
    assert first.show.slug is None
    assert first.show.resource_url is None
    assert second.id == "303878"
    assert second.description == ""
    assert second.seen is True


async def test_fetch_show_episodes_sends_id_param() -> None:
    """Send the requested show id as a query param."""
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_EPISODES_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_show_episodes("6947")

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "id": "6947"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_show_episodes_failure(status: int) -> None:
    """Raise Error when fetching show episodes fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_show_episodes("6947")


EPISODES_TO_WATCH_PAYLOAD: dict[str, Any] = {
    "shows": [
        {
            "id": 38605,
            "title": "Achtsam Morden",
            "remaining": 8,
            "unseen": [
                {
                    "id": 3905073,
                    "title": "Urlaub",
                    "season": 2,
                    "episode": 1,
                    "show": {"id": 38605, "title": "Achtsam Morden", "poster": "https://pictures.betaseries.com/p.jpg"},
                    "code": "S02E01",
                    "description": "Nicole s'embrouille les pinceaux avec ses preuves.",
                    "date": "2026-05-29",
                    "user": {"seen": False},
                    "resource_url": "https://www.betaseries.com/episode/achtsam-morden/s02e01",
                    "platform_links": [{"platform": "Netflix"}],
                }
            ],
        },
        {
            "id": 6947,
            "title": "Below Deck",
            "remaining": 1,
            "unseen": [
                {
                    "id": 303878,
                    "title": "Anchors Aweigh",
                    "season": 1,
                    "episode": 2,
                    "show": {"id": 6947, "title": "Below Deck", "in_account": True},
                    "code": "S01E02",
                    "description": "",
                    "date": "2013-07-09",
                    "user": {"seen": False},
                    "resource_url": "https://www.betaseries.com/episode/below-deck/s01e02",
                    "platform_links": [],
                }
            ],
        },
    ],
    "total": 2,
    "totalEpisodes": 2,
    "errors": [],
}


async def test_fetch_episodes_to_watch_success() -> None:
    """Flatten "shows[].unseen[]" into a single CollectionEpisode, across all shows.

    Verified via Bruno (bruno/Episodes/list.bru) that the payload nests
    episodes under each show, unlike /planning/member or /shows/episodes.
    """
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_TO_WATCH_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_episodes_to_watch()

    assert len(result) == 2
    first, second = tuple(result)
    assert first.id == "3905073"
    assert first.show.id == "38605"
    assert first.show.title == "Achtsam Morden"
    assert second.id == "303878"
    assert second.show.id == "6947"
    assert second.show.title == "Below Deck"

    # Nothing is excluded unless the caller asks for it.
    assert "excludes" not in session.get_calls[0][1]["params"]


async def test_fetch_episodes_to_watch_can_exclude_the_cast() -> None:
    """Send excludes=characters only when the caller opted in."""
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_TO_WATCH_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_episodes_to_watch(exclude_characters=True)

    assert session.get_calls[0][1]["params"]["excludes"] == "characters"


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_episodes_to_watch_failure(status: int) -> None:
    """Raise Error when fetching episodes to watch fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_episodes_to_watch()


async def test_fetch_episodes_to_watch_by_show_success() -> None:
    """Keep "shows[].unseen[]" grouped by show, instead of flattening it.

    Same payload as fetch_episodes_to_watch(), but each Show comes back
    with its own `episodes` already populated.
    """
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_TO_WATCH_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_episodes_to_watch_by_show()

    achtsam_morden = result.for_show("38605")
    assert achtsam_morden is not None
    assert achtsam_morden.title == "Achtsam Morden"
    assert achtsam_morden.episodes is not None
    assert len(achtsam_morden.episodes) == 1
    assert next(iter(achtsam_morden.episodes)).id == "3905073"

    below_deck = result.for_show("6947")
    assert below_deck is not None
    assert below_deck.episodes is not None
    assert next(iter(below_deck.episodes)).id == "303878"


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_episodes_to_watch_by_show_failure(status: int) -> None:
    """Raise Error when fetching episodes to watch fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_episodes_to_watch_by_show()


SHOW_SINGLE_PAYLOAD: dict[str, Any] = {
    "show": {
        "id": 38605,
        "title": "Achtsam Morden",
        "description": "Un avocat véreux devient tueur à gages malgré lui.",
        "slug": "achtsam-morden",
        "original_title": "Achtsam Morden",
        "imdb_id": "tt30217222",
        "themoviedb_id": 252372,
        "genres": {"Comedy": "Comédie", "Crime": "Crime", "Drama": "Drame", "Thriller": "Thriller"},
        "showrunners": [{"id": "900934", "name": "Karsten Dusse", "slug": "karsten-dusse", "picture": None}],
        "aliases": {"114873": "Achtsam Morden", "126382": "Assassino Zen"},
        "seasons": "2",
        "followers": "5974",
        "network": "Netflix",
        "country": "Allemagne",
        "originalLanguage": "allemand",
        "length": "30",
        "rating": "",
        "notes": {"total": 164, "mean": 3.89024, "user": 0},
        "next_trailer": "ZDdijwdg7s8",
        "resource_url": "https://www.betaseries.com/serie/achtsam-morden",
        "images": {
            "show": "https://pictures.betaseries.com/fonds/show/38605_a.jpg",
            "banner": None,
            "box": None,
            "poster": "https://pictures.betaseries.com/fonds/poster/a.jpg",
        },
    },
    "errors": [],
}

SHOW_MULTIPLE_PAYLOAD: dict[str, Any] = {
    "shows": [
        SHOW_SINGLE_PAYLOAD["show"],
        {
            "id": 38606,
            "title": "Das Streben nach Glück",
            "original_title": "Das Streben nach Glück",
            "imdb_id": "",
            "themoviedb_id": 0,
            "genres": {"Drama": "Drame"},
            "showrunners": [],
            "aliases": {"114876": "Das Streben nach Glück"},
            "seasons": "0",
            "followers": "0",
            "network": "",
            "country": None,
            "originalLanguage": None,
            "length": "0",
            "rating": "",
            "notes": {"total": 0, "mean": 0, "user": 0},
            "next_trailer": None,
            "resource_url": "https://www.betaseries.com/serie/das-streben-nach-gluck",
            "images": {"show": None, "banner": None, "box": None, "poster": None},
        },
    ],
    "errors": [],
}


async def test_fetch_shows_single_id_success() -> None:
    """Return a CollectionShow built from the singular "show" key (one id requested).

    Verifies every field of Show and its nested additional_information, including images.
    """
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_SINGLE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    show = result.for_show("38605")
    assert show is not None
    assert show.id == "38605"
    assert show.title == "Achtsam Morden"
    assert show.description == "Un avocat véreux devient tueur à gages malgré lui."
    assert show.slug == "achtsam-morden"
    assert show.resource_url == "https://www.betaseries.com/serie/achtsam-morden"

    info = show.additional_information
    assert info is not None
    assert info.original_title == "Achtsam Morden"
    assert info.imdb_id == "tt30217222"
    assert info.themoviedb_id == "252372"
    assert info.genres == ("Comédie", "Crime", "Drame", "Thriller")
    assert info.showrunners == ("Karsten Dusse",)
    assert info.aliases == ("Achtsam Morden", "Assassino Zen")
    assert info.seasons == 2
    assert info.followers == 5974
    assert info.network == "Netflix"
    assert info.country == "Allemagne"
    assert info.original_language == "allemand"
    assert info.length == 30
    assert info.rating == ""
    assert info.notes_mean == 3.89024
    assert info.notes_total == 164
    assert info.next_trailer == "ZDdijwdg7s8"
    assert info.resource_url == "https://www.betaseries.com/serie/achtsam-morden"
    assert info.images.poster == "https://pictures.betaseries.com/fonds/poster/a.jpg"


async def test_fetch_shows_multiple_ids_success() -> None:
    """Return a CollectionShow built from the plural "shows" key (several ids requested)."""
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_MULTIPLE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605", "38606"])

    assert result.for_show("38605") is not None
    second = result.for_show("38606")
    assert second is not None
    assert second.title == "Das Streben nach Glück"


async def test_fetch_shows_normalizes_empty_and_zero_ids() -> None:
    """Normalize an empty imdb_id and a zero themoviedb_id to None, and empty showrunners/genres."""
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_MULTIPLE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605", "38606"])

    info = result.for_show("38606")
    assert info is not None
    assert info.description is None
    assert info.slug is None
    assert info.additional_information is not None
    assert info.additional_information.imdb_id is None
    assert info.additional_information.themoviedb_id is None
    assert info.additional_information.showrunners == ()
    assert info.additional_information.country is None
    assert info.additional_information.original_language is None
    assert info.additional_information.next_trailer is None
    assert info.additional_information.seasons == 0
    assert info.additional_information.followers == 0


async def test_fetch_shows_tolerates_missing_optional_fields() -> None:
    """Parse a show whose payload is missing every non-essential field.

    /shows/display returns the richest and most variable payload this client
    consumes: a missing key must degrade that show's optional details rather
    than raise a KeyError that fails the whole refresh.
    """
    payload = {"shows": [{"id": "38605", "title": "Achtsam Morden"}]}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    show = result.for_show("38605")
    assert show is not None
    assert show.title == "Achtsam Morden"
    info = show.additional_information
    assert info is not None
    assert info.original_title == ""
    assert info.network == ""
    assert info.rating == ""
    assert info.resource_url == ""
    assert info.seasons == 0
    assert info.followers == 0
    assert info.length == 0


async def test_fetch_shows_tolerates_non_numeric_values() -> None:
    """Fall back to 0 for a numeric field that is not parseable as an int."""
    payload = {"shows": [{"id": "38605", "title": "Achtsam Morden", "seasons": "n/a", "length": None}]}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    show = result.for_show("38605")
    assert show is not None
    assert show.additional_information is not None
    assert show.additional_information.seasons == 0
    assert show.additional_information.length == 0


async def test_fetch_shows_normalizes_null_notes() -> None:
    """Fall back to 0 when "notes" holds explicit nulls rather than omitting the keys.

    A two-argument .get("mean", 0) would only cover a missing key and would
    let an explicit null through, breaking the declared float/int types.
    """
    payload = {"shows": [{"id": "38605", "title": "Achtsam Morden", "notes": {"mean": None, "total": None}}]}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    show = result.for_show("38605")
    assert show is not None
    assert show.additional_information is not None
    assert show.additional_information.notes_mean == 0
    assert show.additional_information.notes_total == 0


async def test_fetch_shows_skips_showrunners_without_a_name() -> None:
    """Drop showrunner entries missing a "name" instead of raising a KeyError."""
    payload = {
        "shows": [
            {
                "id": "38605",
                "title": "Achtsam Morden",
                "showrunners": [{"id": "1"}, {"id": "2", "name": "Karsten Dusse"}],
            }
        ]
    }
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    show = result.for_show("38605")
    assert show is not None
    assert show.additional_information is not None
    assert show.additional_information.showrunners == ("Karsten Dusse",)


async def test_fetch_shows_unknown_show_returns_none() -> None:
    """Return None from for_show() for a show id absent from the response."""
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_SINGLE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_shows(["38605"])

    assert result.for_show("unknown") is None


async def test_fetch_shows_sends_comma_joined_ids() -> None:
    """Join multiple show ids with a comma in the "id" query param."""
    session = FakeSession(get_responses=[FakeResponse(200, SHOW_MULTIPLE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_shows(["38605", "38606"])

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "id": "38605,38606"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_shows_failure(status: int) -> None:
    """Raise Error when fetching shows fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_shows(["38605"])


EPISODES_DISPLAY_PAYLOAD: dict[str, Any] = {
    "episodes": [
        {
            "id": 38605,
            "title": "Cat's Bell",
            "season": 1,
            "episode": 13,
            "code": "S01E13",
            "description": "",
            "date": "1997-07-04",
            "user": {"seen": False},
            "show": {"id": 1485, "title": "Hyper Police", "slug": "hyperpolice"},
            "platform_links": [],
            "resource_url": "https://www.betaseries.com/episode/hyperpolice/s01e13",
        },
        {
            "id": 38606,
            "title": "Another One",
            "season": 1,
            "episode": 14,
            "code": "S01E14",
            "description": "",
            "date": "1997-07-11",
            "user": {"seen": True},
            "show": {"id": 1485, "title": "Hyper Police", "slug": "hyperpolice"},
            "platform_links": [],
            "resource_url": "https://www.betaseries.com/episode/hyperpolice/s01e14",
        },
    ],
    "errors": [],
}


async def test_fetch_episodes_by_id_success() -> None:
    """Return a CollectionEpisode built from the JSON payload on HTTP 200."""
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_DISPLAY_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_episodes_by_id(["38605", "38606"])

    assert len(result) == 2
    first, second = tuple(result)
    assert first.id == "38605"
    assert first.show.id == "1485"
    assert first.show.title == "Hyper Police"
    assert second.id == "38606"
    assert second.seen is True


async def test_fetch_episodes_by_id_deduplicates_shared_show() -> None:
    """Reuse a single Show instance across episodes referencing the same show id."""
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_DISPLAY_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_episodes_by_id(["38605", "38606"])

    first, second = tuple(result)
    assert first.show is second.show


async def test_fetch_episodes_by_id_sends_comma_joined_ids() -> None:
    """Join multiple episode ids with a comma in the "id" query param."""
    session = FakeSession(get_responses=[FakeResponse(200, EPISODES_DISPLAY_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_episodes_by_id(["38605", "38606"])

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "id": "38605,38606"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_episodes_by_id_failure(status: int) -> None:
    """Raise Error when fetching episodes by id fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_episodes_by_id(["38605"])


TIMELINE_PAYLOAD: dict[str, Any] = {
    "events": [
        {
            "id": 2220001980,
            "type": "badge",
            "ref": None,
            "ref_id": 285,
            "date": "2026-07-26 12:18:50",
        },
        {
            "id": 2219944567,
            "type": "markas",
            "ref": "3965195",
            "ref_id": 3965195,
            "date": "2026-07-26 05:20:30",
        },
        {
            "id": 2219941369,
            "type": "season_watched",
            "ref": "13381.1",
            "ref_id": 0,
            "date": "2026-07-26 03:49:26",
        },
        {
            "id": 2216743213,
            "type": "add_serie",
            "ref": None,
            "ref_id": 31940,
            "date": "2026-07-16 23:09:04",
        },
    ],
    "errors": [],
}


async def test_fetch_timeline_success() -> None:
    """Return a CollectionTimelineEvent with only the modeled event types kept.

    "badge" and "add_serie" aren't modeled yet (see timeline_event_type.py) -
    they're silently dropped rather than failing the whole fetch.
    """
    session = FakeSession(get_responses=[FakeResponse(200, TIMELINE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_timeline("42")

    assert len(result) == 2
    episode_event, season_event = tuple(result)
    assert isinstance(episode_event, EpisodeWatchedEvent)
    assert episode_event.id == "2219944567"
    assert episode_event.episode_id == "3965195"
    assert episode_event.date == datetime(2026, 7, 26, 5, 20, 30)  # noqa: DTZ001 (API doesn't return a timezone)
    assert isinstance(season_event, SeasonWatchedEvent)
    assert season_event.id == "2219941369"
    assert season_event.show_id == "13381"
    assert season_event.season == 1
    assert season_event.date == datetime(2026, 7, 26, 3, 49, 26)  # noqa: DTZ001 (API doesn't return a timezone)


async def test_fetch_timeline_drops_unrecognized_type() -> None:
    """Drop an event whose "type" doesn't match any known TimelineEventType value."""
    payload = {
        "events": [{"id": 1, "type": "some_future_event_type", "ref": None, "ref_id": 0, "date": "2026-01-01 00:00:00"}]
    }
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_timeline("42")

    assert len(result) == 0


@pytest.mark.parametrize(
    "ref",
    [
        "not-a-valid-ref",  # no dot: "ref".split(".") unpacking fails
        "123.abc",  # season isn't numeric: int(season) fails
    ],
)
async def test_fetch_timeline_drops_season_watched_with_malformed_ref(ref: str) -> None:
    """Drop a SEASON_WATCHED event whose "ref" doesn't match "{show_id}.{season}".

    Regression test: a malformed ref used to raise an uncaught ValueError
    (from "ref".split(".") unpacking or int(season)), failing the whole
    fetch over a single bad entry instead of just dropping it.

    Args:
        ref (str): The malformed "ref" value to test.

    """
    payload = {"events": [{"id": 1, "type": "season_watched", "ref": ref, "ref_id": 0, "date": "2026-01-01 00:00:00"}]}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_timeline("42")

    assert len(result) == 0


async def test_fetch_timeline_sends_member_id_param_and_omits_optional_ones_by_default() -> None:
    """Send the member id as the "id" query param, omitting nbpp/since_id/last_id/types when not passed."""
    session = FakeSession(get_responses=[FakeResponse(200, TIMELINE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_timeline("42")

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "id": "42"}


async def test_fetch_timeline_sends_optional_params_when_given() -> None:
    """Send nbpp/since_id/last_id/types only when explicitly passed."""
    session = FakeSession(get_responses=[FakeResponse(200, TIMELINE_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_timeline(
        "42",
        nbpp=50,
        since_id="100",
        last_id="200",
        types=[TimelineEventType.EPISODE_WATCHED, TimelineEventType.SEASON_WATCHED],
    )

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {
        "locale": "fr",
        "id": "42",
        "nbpp": "50",
        "since_id": "100",
        "last_id": "200",
        "types": "markas,season_watched",
    }


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_timeline_failure(status: int) -> None:
    """Raise Error when fetching the timeline fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_timeline("42")


async def test_fetch_timeline_raises_auth_error_on_invalid_credentials() -> None:
    """Raise AuthError on HTTP 400 with BetaSeries' "invalid credentials" error code."""
    payload = {"errors": [{"code": 2001, "text": "Données d'identification incorrectes."}]}
    session = FakeSession(get_responses=[FakeResponse(400, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await client.fetch_timeline("42")


BADGES_PAYLOAD: dict[str, Any] = {
    "badges": [
        {
            "id": 64,
            "code": "regarde_moi",
            "name": "Regarde-moi",
            "description": "Un mois s'est écoulé et 30 épisodes ont été regardés.",
            "date": "2013-09-01 22:45:26",
            "height": 256,
            "width": 256,
            "level": None,
        },
        {
            "id": 1,
            "code": "debutant",
            "name": "Débutant",
            "description": "Vous avez regardé votre premier épisode.",
            "date": "2013-08-15 10:00:00",
            "height": 256,
            "width": 256,
            "level": None,
        },
        {
            "id": 282,
            "code": "gi_joe",
            "name": "G.I. Joe",
            "description": "Vous avez regardé 50 séries américaines.",
            "date": "2020-11-13 04:14:58",
            "height": None,
            "width": None,
            "level": 10,
        },
    ],
    "total": 3,
    "errors": [],
}


async def test_fetch_badges_success() -> None:
    """Return a CollectionBadge built from the JSON payload, sorted by date earned."""
    session = FakeSession(get_responses=[FakeResponse(200, BADGES_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_badges("42")

    badges = list(result)
    # Sorted oldest-first by date, regardless of payload order (see BADGES_PAYLOAD above).
    assert [badge.code for badge in badges] == ["debutant", "regarde_moi", "gi_joe"]

    debutant = badges[0]
    assert debutant.id == "1"
    assert debutant.name == "Débutant"
    assert debutant.description == "Vous avez regardé votre premier épisode."
    assert debutant.date == datetime(2013, 8, 15, 10, 0, 0)  # noqa: DTZ001 (API doesn't return a timezone)
    assert debutant.height == 256
    assert debutant.width == 256
    assert debutant.level is None

    gi_joe = badges[2]
    assert gi_joe.height is None
    assert gi_joe.width is None
    assert gi_joe.level == 10


async def test_fetch_badges_sends_member_id() -> None:
    """Send the member id in the "id" query param."""
    session = FakeSession(get_responses=[FakeResponse(200, BADGES_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_badges("42")

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"locale": "fr", "id": "42"}


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_badges_failure(status: int) -> None:
    """Raise Error when fetching badges fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_badges("42")


async def test_fetch_badges_raises_auth_error_on_invalid_credentials() -> None:
    """Raise AuthError on HTTP 400 with BetaSeries' "invalid credentials" error code."""
    payload = {"errors": [{"code": 2001, "text": "Données d'identification incorrectes."}]}
    session = FakeSession(get_responses=[FakeResponse(400, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await client.fetch_badges("42")


async def test_fetch_watch_list_success() -> None:
    """Parse the shows to watch, their remaining count and the global counters."""
    payload = {
        "shows": [
            {
                "id": 38605,
                "title": "Achtsam Morden",
                "remaining": 8,
                "unseen": [
                    {
                        "id": 3905073,
                        "title": "Urlaub",
                        "season": 2,
                        "episode": 1,
                        "code": "S02E01",
                        "description": "A summary.",
                        "date": "2026-05-29",
                        "user": {"seen": False},
                        "platform_links": [{"platform": "Netflix"}],
                        "resource_url": "https://www.betaseries.com/episode/3905073",
                        "show": {
                            "id": 38605,
                            "title": "Achtsam Morden",
                            "poster": "https://pictures.betaseries.com/poster.jpg",
                        },
                    }
                ],
            }
        ],
        "total": 37,
        "totalEpisodes": 726,
    }
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    shows, total_shows, total_episodes = await client.fetch_watch_list(10, 2)

    # The counters are the endpoint's own, unaffected by the requested limits.
    assert total_shows == 37
    assert total_episodes == 726
    assert len(shows) == 1
    assert shows.show_ids == frozenset({"38605"})

    show = next(iter(shows))
    assert show.id == "38605"
    assert show.remaining == 8
    assert show.poster == "https://pictures.betaseries.com/poster.jpg"
    assert next(iter(show.episodes)).code == "S02E01"

    assert session.get_calls[0][1]["params"]["showsLimit"] == "10"
    assert session.get_calls[0][1]["params"]["limit"] == "2"
    # Nothing is excluded unless the caller asks for it.
    assert "excludes" not in session.get_calls[0][1]["params"]


async def test_fetch_watch_list_can_exclude_the_cast() -> None:
    """Send excludes=characters only when the caller opted in."""
    payload = {"shows": [], "total": 0, "totalEpisodes": 0}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_watch_list(10, 2, exclude_characters=True)

    assert session.get_calls[0][1]["params"]["excludes"] == "characters"


async def test_fetch_watch_list_tolerates_a_show_without_episodes() -> None:
    """Fall back to no poster when a listed show carries no unseen episode."""
    payload = {"shows": [{"id": 38605, "title": "Achtsam Morden", "unseen": []}]}
    session = FakeSession(get_responses=[FakeResponse(200, payload)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    shows, total_shows, _total_episodes = await client.fetch_watch_list(10, 2)

    show = next(iter(shows))
    assert show.poster is None
    assert show.remaining == 0
    assert not tuple(show.episodes)
    assert total_shows == 0


@pytest.mark.parametrize(
    "transport_error",
    [aiohttp.ClientConnectionError("cannot connect"), TimeoutError()],
    ids=["connection", "timeout"],
)
async def test_transport_failure_surfaces_as_error_never_auth_error(transport_error: Exception) -> None:
    """Wrap aiohttp's own failures into Error - and deliberately not AuthError.

    Callers read AuthError as "BetaSeries rejected the credentials" and answer
    it by prompting the user to authenticate again (see coordinator.py). A
    network blip must therefore never surface as one, or every outage would
    ask the user to reauthenticate. It also carries no status/body, since the
    request never got a response at all.
    """
    session = FakeSession(get_responses=[transport_error])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error) as raised:
        await client.fetch_member_data()

    assert not isinstance(raised.value, AuthError)
    assert raised.value.__cause__ is transport_error
    assert raised.value.status is None
    assert raised.value.body is None
