"""Shared error-handling tests for every BetaSeries coordinator.

Both coordinators translate the client's exceptions the same way
(AuthError -> ConfigEntryAuthFailed, Error -> UpdateFailed); this is
parametrized here instead of duplicated per coordinator test file.
"""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_watch_list_show import CollectionWatchListShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.exceptions import AuthError, Error
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.watch_list_show import WatchListShow
from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator, PlanningCoordinator, WatchListCoordinator
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from tests.conftest import client_mock

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import AsyncMock

    from custom_components.betaseries.coordinator import BetaSeriesConfigEntry

    from homeassistant.core import HomeAssistant

COORDINATOR_PARAMS = [
    (MemberCoordinator, "fetch_member_data"),
    (PlanningCoordinator, "fetch_planning"),
    (WatchListCoordinator, "fetch_watch_list"),
]


@pytest.mark.parametrize(("coordinator_class", "mocked_method"), COORDINATOR_PARAMS)
async def test_auth_error_marks_refresh_failed(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    mocked_method: str,
) -> None:
    """Mark the refresh as failed with a ConfigEntryAuthFailed when the token is rejected."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    getattr(mock_client, mocked_method).side_effect = AuthError("Access token was rejected")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


@pytest.mark.parametrize(("coordinator_class", "mocked_method"), COORDINATOR_PARAMS)
async def test_auth_error_logs_reauth_guidance(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    mocked_method: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log a warning naming the account, the raw BetaSeries error compacted to one line, and reauthentication.

    The client itself never logs (see AuthError's docstring) - it attaches
    the response's status/body to the exception, and this asserts the
    coordinator actually surfaces them in its own log line, collapsed to a
    single line even though BetaSeries pretty-prints its error bodies.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="Test Account")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    getattr(mock_client, mocked_method).side_effect = AuthError(
        "Access token was rejected",
        status=400,
        body='{\n    "errors": [\n        {\n            "code": 1001,\n            "text": "Mauvaise clé API."\n        }\n    ]\n}',
    )

    coordinator = coordinator_class(hass, entry, mock_client)
    with caplog.at_level(logging.WARNING):
        await coordinator.async_refresh()

    assert "Test Account" in caplog.text
    assert "reauthentication" in caplog.text
    assert '{ "errors": [ { "code": 1001, "text": "Mauvaise clé API." } ] }' in caplog.text


@pytest.mark.parametrize(("coordinator_class", "mocked_method"), COORDINATOR_PARAMS)
async def test_error_marks_refresh_failed(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    mocked_method: str,
) -> None:
    """Mark the refresh as failed with an UpdateFailed on any other client error."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    getattr(mock_client, mocked_method).side_effect = Error("boom")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


# An episode and a watch list, only detailed enough that each coordinator ends
# up with one show id to fetch details for - which is what makes fetch_shows()
# run at all. With an empty planning or an empty list there is nothing missing
# from the cache, the call never happens, and the tests below would pass while
# asserting nothing.
_EPISODE = Episode(
    id="1001",
    season=3,
    number=4,
    code="S03E04",
    title="The One With The Tests",
    description="",
    air_date=date(2026, 8, 1),
    seen=False,
    platforms=(),
    resource_url="https://www.betaseries.com/episode/1001",
    show=Show(id="55", title="Example Show"),
)


def _planning_client() -> AsyncMock:
    """Build a client whose planning holds one show, so its details get fetched."""
    client = client_mock()
    client.fetch_planning.return_value = CollectionEpisode((_EPISODE,))
    return client


def _watch_list_client() -> AsyncMock:
    """Build a client whose watch list holds one show, so its details get fetched."""
    client = client_mock()
    client.fetch_watch_list.return_value = (
        CollectionWatchListShow(
            (WatchListShow(id="55", title="Example Show", remaining=1, poster=None, episodes=CollectionEpisode(())),)
        ),
        1,
        1,
    )
    return client


@pytest.mark.parametrize(
    ("coordinator_class", "make_client"),
    [(PlanningCoordinator, _planning_client), (WatchListCoordinator, _watch_list_client)],
    ids=["planning", "watch_list"],
)
async def test_auth_error_while_fetching_show_details_still_asks_for_reauth(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    make_client: Callable[[], AsyncMock],
) -> None:
    """Surface a rejected token even when it is the artwork call that hits it.

    Show details are decoration, so their failures are absorbed rather than
    taking the entity down - but AuthError subclasses Error, so absorbing
    every Error used to swallow the one failure that must not be: the entry
    stayed loaded with valid-looking data and never prompted for
    reauthentication, while every subsequent request was rejected too.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = make_client()
    mock_client.fetch_shows.side_effect = AuthError("Access token was rejected")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    # The main call succeeded, so only the details call can have failed.
    assert mock_client.fetch_shows.await_count == 1
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
