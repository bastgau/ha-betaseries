"""Data update coordinator for the BetaSeries integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .betaseries import AuthError, Error
from .const import DEFAULT_MEMBER_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .betaseries import Client, MemberData

_LOGGER = logging.getLogger(__name__)

type BetaSeriesConfigEntry = ConfigEntry["MemberCoordinator"]


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
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_MEMBER_SCAN_INTERVAL,
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
        try:
            return await self.client.fetch_member_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(str(err)) from err
