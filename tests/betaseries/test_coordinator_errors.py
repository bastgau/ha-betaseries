"""Shared error-handling tests for every BetaSeries coordinator.

Both coordinators translate the client's exceptions the same way
(AuthError -> ConfigEntryAuthFailed, Error -> UpdateFailed); this is
parametrized here instead of duplicated per coordinator test file.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.betaseries.betaseries.exceptions import AuthError, Error
from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import EpisodeCoordinator, MemberCoordinator, PlanningCoordinator
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
    (EpisodeCoordinator, "fetch_watch_list"),
]


@pytest.mark.parametrize(("coordinator_class", "mocked_method"), COORDINATOR_PARAMS)
async def test_auth_error_marks_refresh_failed(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    mocked_method: str,
) -> None:
    """Mark the refresh as failed with a ConfigEntryAuthFailed when the token is rejected.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        coordinator_class (Callable): The coordinator class under test.
        mocked_method (str): Name of the client method this coordinator calls.

    """
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

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        coordinator_class (Callable): The coordinator class under test.
        mocked_method (str): Name of the client method this coordinator calls.
        caplog (pytest.LogCaptureFixture): Captures log records emitted during the test.

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
    """Mark the refresh as failed with an UpdateFailed on any other client error.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        coordinator_class (Callable): The coordinator class under test.
        mocked_method (str): Name of the client method this coordinator calls.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = client_mock()
    getattr(mock_client, mocked_method).side_effect = Error("boom")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
