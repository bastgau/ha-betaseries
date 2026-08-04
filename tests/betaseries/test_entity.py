"""Tests for BetaSeriesEntity (base entity)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import DOMAIN
from custom_components.betaseries.coordinator import (
    BetaSeriesData,
    MemberCoordinator,
    PlanningCoordinator,
    WatchListCoordinator,
)
from custom_components.betaseries.entity import BetaSeriesEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers.entity import EntityDescription

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ENTITY_DESCRIPTION = EntityDescription(key="episodes_to_watch")

STATS = MemberStats(
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
)


def _entry_with_member(hass: HomeAssistant, *, title: str, login: str) -> MockConfigEntry:
    """Set up an entry whose runtime data holds a refreshed member coordinator.

    Entities read the account's login through runtime_data, so it has to be
    populated here the way async_setup_entry does before forwarding platforms.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title=title)
    entry.add_to_hass(hass)

    client = AsyncMock()
    member = MemberCoordinator(hass, entry, client)
    member.data = MemberData(identity=MemberIdentity(id="42", login=login), stats=STATS)
    entry.runtime_data = BetaSeriesData(
        member=member,
        planning=PlanningCoordinator(hass, entry, client),
        watch_list=WatchListCoordinator(hass, entry, client),
    )
    return entry


async def test_unique_id_and_device_info(hass: HomeAssistant) -> None:
    """Derive unique_id and device info from the config entry and the account."""
    entry = _entry_with_member(hass, title="test_user", login="test_user")

    entity = BetaSeriesEntity(entry.runtime_data.member, ENTITY_DESCRIPTION)

    assert entity.unique_id == "42_episodes_to_watch"
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {(DOMAIN, "42")}
    assert entity.device_info["name"] == "BetaSeries - test_user"
    assert entity.device_info["manufacturer"] == "BetaSeries"
    assert entity.device_info["model"] == "Member Account"
    assert entity.device_info["configuration_url"] == "https://www.betaseries.com/membre/test_user"


async def test_device_info_survives_a_renamed_entry(hass: HomeAssistant) -> None:
    """Keep naming the device - and linking to the profile - after the entry is renamed.

    The title only starts out as the login: Home Assistant lets anyone rename
    a config entry, and it used to be what both the device name and the
    profile URL were built from. Renaming to "Bastien's shows" pointed the
    device's "Visit device" link at betaseries.com/membre/Bastien's shows.
    """
    entry = _entry_with_member(hass, title="Bastien's shows", login="test_user")

    entity = BetaSeriesEntity(entry.runtime_data.member, ENTITY_DESCRIPTION)

    assert entity.device_info is not None
    assert entity.device_info["name"] == "BetaSeries - test_user"
    assert entity.device_info["configuration_url"] == "https://www.betaseries.com/membre/test_user"
