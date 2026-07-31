"""Tests for MemberCoordinator.

Client error handling (AuthError/Error translation) is covered by the
shared, parametrized tests in test_coordinator_errors.py instead of here.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.badge import Badge
from custom_components.betaseries.betaseries.collection_badge import CollectionBadge
from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import BADGES_STORE_KEY_PREFIX, CONF_MEMBER_SCAN_INTERVAL, DOMAIN
from custom_components.betaseries.coordinator import MemberCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from typing import Any

    import pytest

    from homeassistant.core import HomeAssistant

BADGE = Badge(
    id="1",
    code="debutant",
    name="Débutant",
    description="Vous avez regardé votre premier épisode.",
    date=datetime(2013, 8, 15, 10, 0, 0),  # noqa: DTZ001 (API doesn't return a timezone)
    height=256,
    width=256,
    level=None,
)

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


async def test_uses_default_scan_interval(hass: HomeAssistant) -> None:
    """Default to 15 minutes when no member_scan_interval option is set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)

    coordinator = MemberCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=15)


async def test_uses_configured_scan_interval(hass: HomeAssistant) -> None:
    """Use the member_scan_interval option when set."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", options={CONF_MEMBER_SCAN_INTERVAL: 30})
    entry.add_to_hass(hass)

    coordinator = MemberCoordinator(hass, entry, AsyncMock())

    assert coordinator.update_interval == timedelta(minutes=30)


async def test_update_success(hass: HomeAssistant) -> None:
    """Store the member data fetched from the client after a successful refresh."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = MEMBER_DATA.badges

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == MEMBER_DATA


async def test_first_refresh_fetches_badges(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Fetch badge details on the first refresh, with an empty cache."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert mock_client.fetch_badges.await_count == 1
    assert tuple(coordinator.data.badges) == (BADGE,)


async def test_unchanged_badge_count_is_not_refetched(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Reuse the cached badge details when stats.badges hasn't changed since the last refresh."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    mock_client.fetch_badges.reset_mock()
    await coordinator.async_refresh()

    assert mock_client.fetch_badges.await_count == 0
    assert tuple(coordinator.data.badges) == (BADGE,)


async def test_changed_badge_count_triggers_refetch(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Refetch badge details when stats.badges differs from the last known count."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    new_badge = dataclasses.replace(BADGE, id="282", code="gi_joe")
    updated_member_data = dataclasses.replace(
        MEMBER_DATA, stats=dataclasses.replace(MEMBER_DATA.stats, badges=MEMBER_DATA.stats.badges + 1)
    )
    mock_client.fetch_member_data.return_value = updated_member_data
    mock_client.fetch_badges.reset_mock()
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE, new_badge))

    await coordinator.async_refresh()

    assert mock_client.fetch_badges.await_count == 1
    assert tuple(coordinator.data.badges) == (BADGE, new_badge)


async def test_badges_persist_across_coordinator_instances(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
) -> None:
    """Persist the cached badge details so a new coordinator instance reuses them."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    first_coordinator = MemberCoordinator(hass, entry, mock_client)
    await first_coordinator.async_refresh()

    mock_client.fetch_badges.reset_mock()
    second_coordinator = MemberCoordinator(hass, entry, mock_client)
    await second_coordinator.async_refresh()

    assert mock_client.fetch_badges.await_count == 0
    assert tuple(second_coordinator.data.badges) == (BADGE,)


async def test_incompatible_badges_cache_version_is_discarded_not_crashed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Discard a badges cache from an older, incompatible store version instead of crashing.

    Mirrors _CacheStore's discard-on-migrate behavior (see
    test_planning_coordinator.py::test_incompatible_cache_version_is_discarded_not_crashed):
    this cache is only a performance optimization, so it's always safe/cheap
    to start empty and refetch rather than migrate an incompatible shape.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        hass_storage (dict[str, Any]): The in-memory Store backing, pre-seeded with old data.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42")
    entry.add_to_hass(hass)
    store_key = f"{BADGES_STORE_KEY_PREFIX}_{entry.entry_id}"
    hass_storage[store_key] = {
        "version": 0,
        "minor_version": 1,
        "key": store_key,
        "data": {"unexpected_shape": True},
    }
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert mock_client.fetch_badges.await_count == 1
    assert tuple(coordinator.data.badges) == (BADGE,)


async def test_clean_badges_cache_refetches_even_with_unchanged_count(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],  # noqa: ARG001 - activates the real (in-memory) Store mock  # pylint: disable=unused-argument
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Force a refetch of badge details via the "Refresh badges" button, even if the count is unchanged.

    Regression scenario: a badge's description/level could change on
    BetaSeries' side without stats.badges changing, in which case a normal
    refresh would keep serving the stale cached list forever.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="Test Account")
    entry.add_to_hass(hass)
    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    mock_client.fetch_badges.return_value = CollectionBadge((BADGE,))

    coordinator = MemberCoordinator(hass, entry, mock_client)
    await coordinator.async_refresh()
    assert mock_client.fetch_badges.await_count == 1

    updated_badge = dataclasses.replace(BADGE, description="Updated description.")
    mock_client.fetch_badges.reset_mock()
    mock_client.fetch_badges.return_value = CollectionBadge((updated_badge,))

    with caplog.at_level(logging.DEBUG):
        await coordinator.async_clean_badges_cache()
    await hass.async_block_till_done()

    assert mock_client.fetch_badges.await_count == 1
    assert tuple(coordinator.data.badges) == (updated_badge,)
    assert "Clearing cached badges for Test Account" in caplog.text
