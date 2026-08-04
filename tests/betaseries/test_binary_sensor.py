"""Tests for BetaSeries binary sensor entities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.member_data import MemberData
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.betaseries.member_stats import MemberStats
from custom_components.betaseries.const import DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET, STATE_OFF, STATE_ON

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret", "access_token": "token123"}
SAVED_DATA = {CONF_API_KEY: "test-api-key", "access_token": "token123"}


def _member_data(*, episodes_to_watch: int, movies_to_watch: int) -> MemberData:
    """Create test MemberData with specified watch counts."""
    return MemberData(
        identity=MemberIdentity(id="42", login="test_user"),
        stats=MemberStats(
            xp=1337,
            episodes_to_watch=episodes_to_watch,
            time_to_spend=540,
            progress=77.4699,
            shows_to_watch=3,
            movies_to_watch=movies_to_watch,
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


@pytest.mark.parametrize(
    ("episodes_to_watch", "movies_to_watch", "expected_new_episode", "expected_movies_to_watch"),
    [
        (0, 0, STATE_OFF, STATE_OFF),
        (1, 0, STATE_ON, STATE_OFF),
        (0, 1, STATE_OFF, STATE_ON),
        (5, 2, STATE_ON, STATE_ON),
    ],
)
async def test_binary_sensors_reflect_member_data(
    hass: HomeAssistant,
    episodes_to_watch: int,
    movies_to_watch: int,
    expected_new_episode: str,
    expected_movies_to_watch: str,
) -> None:
    """Turn on/off depending on the corresponding counters."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", title="test_user", data=USER_INPUT)
    entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.fetch_member_data.return_value = _member_data(
        episodes_to_watch=episodes_to_watch, movies_to_watch=movies_to_watch
    )

    with patch("custom_components.betaseries.Client", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    new_episode_state = hass.states.get("binary_sensor.betaseries_test_user_episodes_available")
    movies_state = hass.states.get("binary_sensor.betaseries_test_user_movies_available")

    assert new_episode_state is not None
    assert movies_state is not None
    assert new_episode_state.state == expected_new_episode
    assert movies_state.state == expected_movies_to_watch
