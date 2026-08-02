"""Button platform for the BetaSeries integration.

Each button clears one coordinator's cache and refreshes it, so pressing it
re-fetches from BetaSeries even when nothing would normally trigger a
re-fetch - badge details whose count hasn't changed, past planning months
that can no longer change, or show artwork already known. Without these,
that data would never be requested again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .entity import BetaSeriesEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BetaSeriesConfigEntry, MemberCoordinator, PlanningCoordinator, WatchListCoordinator

CLEAR_BADGES_CACHE_DESCRIPTION = ButtonEntityDescription(
    key="clear_badges_cache",
    translation_key="clear_badges_cache",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

CLEAR_PLANNING_CACHE_DESCRIPTION = ButtonEntityDescription(
    key="clear_planning_cache",
    translation_key="clear_planning_cache",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

CLEAR_WATCH_LIST_CACHE_DESCRIPTION = ButtonEntityDescription(
    key="clear_shows_to_catch_up_cache",
    translation_key="clear_shows_to_catch_up_cache",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BetaSeries buttons from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry being set up.
        async_add_entities (AddEntitiesCallback): Callback to register the new entities.

    Returns:
        None: Entities are registered via async_add_entities, nothing is returned.

    """
    async_add_entities(
        [
            BetaSeriesCleanBadgesCacheButton(entry.runtime_data.member, CLEAR_BADGES_CACHE_DESCRIPTION),
            BetaSeriesCleanPlanningCacheButton(entry.runtime_data.planning, CLEAR_PLANNING_CACHE_DESCRIPTION),
            BetaSeriesCleanWatchListCacheButton(entry.runtime_data.watch_list, CLEAR_WATCH_LIST_CACHE_DESCRIPTION),
        ]
    )


class BetaSeriesCleanBadgesCacheButton(BetaSeriesEntity, ButtonEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Force a full refetch of badge details, bypassing the count-based cache.

    Attributes:
        coordinator (MemberCoordinator): The coordinator whose badges_store this button clears.

    """

    coordinator: MemberCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    async def async_press(self) -> None:
        """Clear the cached badge details and refresh now.

        Returns:
            None: The coordinator's data is updated in place.

        """
        await self.coordinator.async_clear_badges_cache()


class BetaSeriesCleanPlanningCacheButton(BetaSeriesEntity, ButtonEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Force a full refetch of the planning, including cached past months.

    Attributes:
        coordinator (PlanningCoordinator): The coordinator whose store this button clears.

    """

    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    async def async_press(self) -> None:
        """Clear the cached past months and refresh now.

        Returns:
            None: The coordinator's data is updated in place.

        """
        await self.coordinator.async_clear_planning_cache()


class BetaSeriesCleanWatchListCacheButton(BetaSeriesEntity, ButtonEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Force a full refetch of the watch list, artwork included.

    Attributes:
        coordinator (WatchListCoordinator): The coordinator whose show_images_store this button clears.

    """

    coordinator: WatchListCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    async def async_press(self) -> None:
        """Clear the cached show images and refresh now.

        Returns:
            None: The coordinator's data is updated in place.

        """
        await self.coordinator.async_clear_watch_list_cache()
