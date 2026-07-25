"""The BetaSeries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .betaseries import Client
from .coordinator import MemberCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import BetaSeriesConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: BetaSeriesConfigEntry) -> bool:
    """Set up BetaSeries from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to set up.

    Returns:
        bool: True if setup succeeded.

    """
    client = Client(async_get_clientsession(hass), entry.data[CONF_API_KEY], entry.data["access_token"])
    coordinator = MemberCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    return True


async def async_unload_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,  # noqa: ARG001
) -> bool:
    """Unload a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to unload.

    Returns:
        bool: True if unload succeeded.

    """
    return True
