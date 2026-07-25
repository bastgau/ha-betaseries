"""Data update coordinator for the BetaSeries integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .betaseries import AuthError, Error
from .const import (
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_SCAN_INTERVAL,
    DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES,
    DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    PLANNING_MONTHS_AHEAD,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .betaseries import Client, MemberData, PlanningEpisode

_LOGGER = logging.getLogger(__name__)

type BetaSeriesConfigEntry = ConfigEntry["BetaSeriesData"]


class MemberCoordinator(DataUpdateCoordinator["MemberData"]):
    """Fetch member data and statistics (GET /members/infos, see CLAUDE.md §5).

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch member data.

    """

    config_entry: BetaSeriesConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BetaSeriesConfigEntry, client: Client) -> None:
        """Initialize the coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
            client (Client): The BetaSeries API client used to fetch member data.

        """
        scan_interval_minutes = config_entry.options.get(
            CONF_MEMBER_SCAN_INTERVAL, DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client

    async def _async_update_data(self) -> MemberData:
        """Fetch the latest member data.

        Returns:
            MemberData: The member's id, login, xp and viewing statistics.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        _LOGGER.debug("Fetching member data from BetaSeries for %s", self.config_entry.title)
        try:
            return await self.client.fetch_member_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(str(err)) from err


class PlanningCoordinator(DataUpdateCoordinator[tuple["PlanningEpisode", ...]]):
    """Fetch the member's planning (GET /planning/member, see CLAUDE.md §4).

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch the planning.

    """

    config_entry: BetaSeriesConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BetaSeriesConfigEntry, client: Client) -> None:
        """Initialize the coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
            client (Client): The BetaSeries API client used to fetch the planning.

        """
        scan_interval_minutes = config_entry.options.get(
            CONF_PLANNING_SCAN_INTERVAL, DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_planning",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client

    async def _async_update_data(self) -> tuple[PlanningEpisode, ...]:
        """Fetch the planning for the current month and PLANNING_MONTHS_AHEAD months ahead.

        Returns:
            tuple[PlanningEpisode, ...]: The member's unseen episodes, in API order.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        _LOGGER.debug("Fetching planning from BetaSeries for %s", self.config_entry.title)
        months = _upcoming_months(dt_util.now().date(), PLANNING_MONTHS_AHEAD)
        try:
            episodes_by_month = [await self.client.fetch_planning(month) for month in months]
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(str(err)) from err

        return tuple(episode for episodes in episodes_by_month for episode in episodes)


@dataclass
class BetaSeriesData:
    """Hold the coordinators stored on the config entry's runtime_data.

    Attributes:
        member (MemberCoordinator): Coordinator for member data/stats (v1).
        planning (PlanningCoordinator): Coordinator for the upcoming episodes planning (v2).

    """

    member: MemberCoordinator
    planning: PlanningCoordinator


def _upcoming_months(today: date, months_ahead: int) -> list[str]:
    """Build the list of "YYYY-MM" strings from this month through months_ahead later.

    Args:
        today (date): Reference date (the current month is always included).
        months_ahead (int): Number of additional months to include after the current one.

    Returns:
        list[str]: Months in chronological order, e.g. ["2026-08", "2026-09", "2026-10"].

    """
    months: list[str] = []
    year, month = today.year, today.month
    for _ in range(months_ahead + 1):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months
