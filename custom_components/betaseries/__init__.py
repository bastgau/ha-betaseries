"""The BetaSeries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .betaseries import Client
from .const import CACHE_STORES, CONF_LOCALE, DEFAULT_LOCALE, DOMAIN
from .coordinator import BetaSeriesData, MemberCoordinator, PlanningCoordinator, WatchListCoordinator
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .coordinator import BetaSeriesConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  # pylint: disable=invalid-name  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]


async def async_setup(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    config: ConfigType,  # noqa: ARG001
) -> bool:
    """Register the BetaSeries services, once per Home Assistant run.

    Services are registered at the domain level (see services.py), not per
    config entry: a single call here covers every BetaSeries account that
    gets added afterward.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config (ConfigType): Unused; this integration has no YAML configuration.

    Returns:
        bool: Always True.

    """
    async_setup_services(hass)
    return True


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
    # watch_list sensor's attribute, so a failure there must not take the
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


async def async_remove_entry(hass: HomeAssistant, entry: BetaSeriesConfigEntry) -> None:
    """Delete the caches this entry persisted, once it is removed.

    Each coordinator keeps its own Store keyed by the entry id (see
    coordinator.py). Home Assistant never deletes those files on its own, so
    without this every add/remove cycle would strand one file per cache in
    .storage indefinitely. They only ever hold refetchable API responses, so
    dropping them costs nothing beyond the next refresh.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry being removed.

    Returns:
        None

    """
    for version, key_prefix in CACHE_STORES:
        # async_remove() already suppresses FileNotFoundError, so caches this
        # entry never happened to write need no special casing here.
        await Store(hass, version, f"{key_prefix}_{entry.entry_id}").async_remove()
