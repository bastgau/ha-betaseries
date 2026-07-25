"""Tests for Client (authenticated data endpoints).

See test_auth.py for why aiohttp.ClientSession is mocked by hand instead of
using aioresponses.
"""

from __future__ import annotations

from datetime import date

from custom_components.betaseries.betaseries.client import Client
from custom_components.betaseries.betaseries.exceptions import Error
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

    assert result.id == "42"
    assert result.login == "test_user"
    assert result.xp == 1337
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


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_member_data_failure(status: int) -> None:
    """Raise Error when fetching member data fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    with pytest.raises(Error):
        await client.fetch_member_data()


PLANNING_PAYLOAD = {
    "episodes": [
        {
            "id": 1001,
            "season": 3,
            "episode": 4,
            "code": "S03E04",
            "title": "The One With The Tests",
            "date": "2026-08-01",
            "user": {"seen": False},
            "show": {"id": 55, "title": "Example Show"},
            "platform_links": [{"platform": "Netflix"}, {"platform": "Apple TV"}],
            "resource_url": "https://www.betaseries.com/episode/1001",
        }
    ]
}


async def test_fetch_planning_success() -> None:
    """Return a tuple of PlanningEpisode built from the JSON payload on HTTP 200."""
    session = FakeSession(get_responses=[FakeResponse(200, PLANNING_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    result = await client.fetch_planning("2026-08")

    assert len(result) == 1
    episode = result[0]
    assert episode.id == "1001"
    assert episode.show_id == "55"
    assert episode.show_title == "Example Show"
    assert episode.season == 3
    assert episode.episode == 4
    assert episode.code == "S03E04"
    assert episode.title == "The One With The Tests"
    assert episode.air_date == date(2026, 8, 1)
    assert episode.seen is False
    assert episode.platforms == ("Netflix", "Apple TV")
    assert episode.resource_url == "https://www.betaseries.com/episode/1001"


async def test_fetch_planning_sends_unseen_and_month_params() -> None:
    """Send unseen=true and the requested month as query params.

    Both params are verified (via Bruno) to filter strictly server-side on
    GET /planning/member, unlike "fields" which that endpoint ignores.
    """
    session = FakeSession(get_responses=[FakeResponse(200, PLANNING_PAYLOAD)])
    client = Client(session, API_KEY, ACCESS_TOKEN)  # type: ignore[arg-type]

    await client.fetch_planning("2026-08")

    _args, kwargs = session.get_calls[0]
    assert kwargs["params"] == {"unseen": "true", "month": "2026-08"}


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
