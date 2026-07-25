"""Shared error-handling tests for MemberCoordinator and PlanningCoordinator.

Both coordinators translate the client's exceptions the same way
(AuthError -> ConfigEntryAuthFailed, Error -> UpdateFailed); this is
parametrized here instead of duplicated per coordinator test file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.exceptions import AuthError, Error
from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator, PlanningCoordinator
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.betaseries.coordinator import BetaSeriesConfigEntry

    from homeassistant.core import HomeAssistant

COORDINATOR_PARAMS = [
    (MemberCoordinator, "fetch_member_data"),
    (PlanningCoordinator, "fetch_planning"),
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
        coordinator_class (Callable): MemberCoordinator or PlanningCoordinator.
        mocked_method (str): Name of the client method this coordinator calls.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    getattr(mock_client, mocked_method).side_effect = AuthError("Access token was rejected")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


@pytest.mark.parametrize(("coordinator_class", "mocked_method"), COORDINATOR_PARAMS)
async def test_error_marks_refresh_failed(
    hass: HomeAssistant,
    coordinator_class: Callable[[HomeAssistant, BetaSeriesConfigEntry, AsyncMock], MemberCoordinator],
    mocked_method: str,
) -> None:
    """Mark the refresh as failed with an UpdateFailed on any other client error.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        coordinator_class (Callable): MemberCoordinator or PlanningCoordinator.
        mocked_method (str): Name of the client method this coordinator calls.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    getattr(mock_client, mocked_method).side_effect = Error("boom")

    coordinator = coordinator_class(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
