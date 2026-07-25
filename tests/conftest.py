"""Shared fixtures for the BetaSeries test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

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


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch async_setup_entry to isolate config flow tests from real setup.

    Yields:
        AsyncMock: The patched async_setup_entry mock.

    """
    with patch("custom_components.betaseries.async_setup_entry", return_value=True) as mock:
        yield mock
