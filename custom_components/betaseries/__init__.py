"""The BetaSeries integration.

Minimal for now: stores the credentials obtained by the config flow so the
entry is loadable. The data coordinator and platforms (sensor, binary_sensor)
are added in a later milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass
class BetaSeriesRuntimeData:
    """Store the credentials kept on the config entry until the coordinator is added.

    Attributes:
        api_key (str): BetaSeries API key (client_id).
        client_secret (str): BetaSeries API client secret.
        access_token (str): BetaSeries OAuth access token.

    """

    api_key: str
    client_secret: str
    access_token: str


type BetaSeriesConfigEntry = ConfigEntry[BetaSeriesRuntimeData]


async def async_setup_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
) -> bool:
    """Set up BetaSeries from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to set up.

    Returns:
        bool: True if setup succeeded.

    """
    entry.runtime_data = BetaSeriesRuntimeData(
        api_key=entry.data[CONF_API_KEY],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        access_token=entry.data["access_token"],
    )
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
