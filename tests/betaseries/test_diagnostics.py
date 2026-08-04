"""Tests for the BetaSeries diagnostics platform."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import patch

from custom_components.betaseries.betaseries.collection_episode import CollectionEpisode
from custom_components.betaseries.betaseries.collection_watch_list_show import CollectionWatchListShow
from custom_components.betaseries.betaseries.episode import Episode
from custom_components.betaseries.betaseries.exceptions import Error
from custom_components.betaseries.betaseries.show import Show
from custom_components.betaseries.betaseries.watch_list_show import WatchListShow
from custom_components.betaseries.const import CONF_PLANNING_MONTHS_BEHIND, DOMAIN
from custom_components.betaseries.diagnostics import async_get_config_entry_diagnostics
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from tests.betaseries.test_sensor import MEMBER_DATA
from tests.conftest import client_mock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SAVED_DATA = {
    CONF_API_KEY: "test-api-key",
    CONF_ACCESS_TOKEN: "token123",
}

EPISODE = Episode(
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

WATCH_LIST = CollectionWatchListShow(
    (
        WatchListShow(
            id="55",
            title="Example Show",
            remaining=12,
            poster=None,
            episodes=CollectionEpisode((EPISODE,)),
        ),
    )
)


async def _setup(hass: HomeAssistant, *, planning_fails: bool = False) -> MockConfigEntry:
    """Set up an entry whose coordinators are backed by a mocked client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="test_user",
        data=SAVED_DATA,
        options={CONF_PLANNING_MONTHS_BEHIND: 0},
    )
    entry.add_to_hass(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.return_value = MEMBER_DATA
    if planning_fails:
        mock_client.fetch_planning.side_effect = Error("planning is down")
    else:
        # One call per month in the window (current + months_ahead), so the
        # episode must be returned once rather than for every month.
        mock_client.fetch_planning.side_effect = [
            CollectionEpisode((EPISODE,)),
            CollectionEpisode(()),
            CollectionEpisode(()),
        ]
    mock_client.fetch_watch_list.return_value = (WATCH_LIST, 37, 726)

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_diagnostics_redact_every_credential(hass: HomeAssistant) -> None:
    """Never let the API key, secret or access token reach the diagnostics file.

    These files are downloaded by users and pasted into public issues, so a
    credential surviving here would be published. The access token alone grants
    full account access.
    """
    entry = await _setup(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    data = result["entry"]["data"]
    assert data[CONF_API_KEY] == "**REDACTED**"
    assert data[CONF_ACCESS_TOKEN] == "**REDACTED**"
    assert "test-api-key" not in str(result)
    assert "token123" not in str(result)


async def test_diagnostics_report_aggregates_only(hass: HomeAssistant) -> None:
    """Report counts and totals, never a show or episode the member follows.

    A viewing history is more personal than a set of counters, and these files
    end up in public issues.
    """
    entry = await _setup(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["planning"]["episodes"] == 1
    # Reported apart: an episode restored from the cache carries no watch
    # status at all, so counting it as unseen would understate the total.
    assert result["planning"]["episodes_seen"] == 0
    assert result["planning"]["episodes_seen_unknown"] == 0
    assert result["planning"]["episodes_per_month"] == {"2026-08": 1}
    assert result["planning"]["shows"] == 1
    assert result["watch_list"]["total_shows"] == 37
    assert result["watch_list"]["total_episodes"] == 726
    assert result["watch_list"]["shows_listed"] == 1
    assert result["member"]["stats"]["episodes_to_watch"] == 12

    # Nothing identifying what is watched.
    rendered = str(result)
    assert "Example Show" not in rendered
    assert "The One With The Tests" not in rendered
    assert "S03E04" not in rendered


async def test_diagnostics_survive_a_failed_coordinator(hass: HomeAssistant) -> None:
    """Still report a failing coordinator's state instead of raising.

    A refresh failure is exactly when someone downloads diagnostics, so the
    blocks whose data is missing must degrade to their refresh state rather
    than take the whole file down.
    """
    entry = await _setup(hass, planning_fails=True)

    result = await async_get_config_entry_diagnostics(hass, entry)

    planning = result["planning"]
    assert planning["last_update_success"] is False
    assert planning["last_error"] is not None
    assert "planning is down" in planning["last_error"]
    assert "episodes" not in planning
    # The cache section is reported either way: it does not depend on the fetch.
    assert planning["cached_months"] == {}
    # The other coordinators are unaffected.
    assert result["member"]["last_update_success"] is True
    assert result["watch_list"]["last_update_success"] is True


async def test_diagnostics_degrade_for_every_failed_coordinator(hass: HomeAssistant) -> None:
    """Report only the refresh state of each coordinator that has no data.

    The member coordinator cannot fail during setup - the entry would not load
    at all - so it is failed on a later refresh, which is how it behaves in
    practice once BetaSeries starts rejecting the stored credentials.
    """
    entry = await _setup(hass)

    mock_client = client_mock()
    mock_client.fetch_member_data.side_effect = Error("member endpoint is down")
    mock_client.fetch_watch_list.side_effect = Error("watch list is down")
    entry.runtime_data.member.client = mock_client
    entry.runtime_data.watch_list.client = mock_client
    await entry.runtime_data.member.async_refresh()
    await entry.runtime_data.watch_list.async_refresh()

    result = await async_get_config_entry_diagnostics(hass, entry)

    for block, message in (("member", "member endpoint is down"), ("watch_list", "watch list is down")):
        assert result[block]["last_update_success"] is False
        assert message in result[block]["last_error"]
    assert "stats" not in result["member"]
    assert "total_shows" not in result["watch_list"]
