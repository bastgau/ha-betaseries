"""The BetaSeries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .betaseries import Client
from .const import CONF_LOCALE, DEFAULT_LOCALE
from .coordinator import BetaSeriesData, MemberCoordinator, PlanningCoordinator, WatchListCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import BetaSeriesConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BetaSeriesConfigEntry) -> bool:
    """Set up BetaSeries from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to set up.

    Returns:
        bool: True if setup succeeded.

    """
    client = Client(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.data["access_token"],
        entry.options.get(CONF_LOCALE, DEFAULT_LOCALE),
    )

    member_coordinator = MemberCoordinator(hass, entry, client)
    planning_coordinator = PlanningCoordinator(hass, entry, client)

    # Only the member data is required for the entry to be usable: it backs the
    # sensors/binary sensors and is the single request that proves the stored
    # credentials still work, so a failure here must retry the whole setup.
    await member_coordinator.async_config_entry_first_refresh()

    # The planning is fetched with async_refresh() (which logs failures instead
    # of raising) so a planning outage degrades to unavailable calendar/next
    # episode entities rather than taking the whole entry - and every member
    # sensor with it - down. It issues up to one request per month in the
    # configured window, against a single one for the member data, so it is by
    # far the likelier of the two to fail. CoordinatorEntity.available already
    # reflects last_update_success, so the affected entities mark themselves
    # unavailable until the next successful refresh with no extra code.
    await planning_coordinator.async_refresh()

    # Same reasoning as the planning: the watch list only backs the
    # shows_to_watch sensor's attribute, so a failure there must not take the
    # whole entry down.
    watch_list_coordinator = WatchListCoordinator(hass, entry, client)
    await watch_list_coordinator.async_refresh()

    entry.runtime_data = BetaSeriesData(
        member=member_coordinator, planning=planning_coordinator, watch_list=watch_list_coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BetaSeriesConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to unload.

    Returns:
        bool: True if unload succeeded.

    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
