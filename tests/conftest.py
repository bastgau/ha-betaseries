"""Shared fixtures for the BetaSeries test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.collection_show import CollectionShow
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(  # pylint: disable=unused-argument
    enable_custom_integrations: None,
) -> None:
    """Enable custom_components/ discovery for every test.

    Args:
        enable_custom_integrations (None): Upstream fixture doing the actual work.

    Returns:
        None: Nothing; the upstream fixture performs the setup.

    """


def client_mock(**kwargs: object) -> AsyncMock:
    """Build a Client mock with a usable default for fetch_shows().

    PlanningCoordinator resolves show posters through
    `(await client.fetch_shows(...)).for_show(...)`. A bare AsyncMock
    propagates asynchronousness to its children, so for_show() - which is
    synchronous - would hand back a coroutine. Returning a real, empty
    CollectionShow keeps posters out of the way of tests that don't care
    about them; poster tests override fetch_shows on the returned mock.

    Args:
        **kwargs (object): Attributes to set on the mock, e.g. fetch_planning=...

    Returns:
        AsyncMock: The configured client mock.

    """
    client = AsyncMock()
    client.fetch_shows.return_value = CollectionShow({})
    for name, value in kwargs.items():
        setattr(client, name, value)
    return client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch async_setup_entry to isolate config flow tests from real setup.

    Yields:
        AsyncMock: The patched async_setup_entry mock.

    """
    with patch("custom_components.betaseries.async_setup_entry", return_value=True) as mock:
        yield mock
