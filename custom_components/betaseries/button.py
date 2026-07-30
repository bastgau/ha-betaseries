"""Button platform for the BetaSeries integration.

Two buttons let the user force a full refetch, bypassing each coordinator's
own caching (badges_store/store - see coordinator.py): "Refresh badges" and
"Refresh planning" clear their respective Store before requesting a refresh,
so pressing them always re-fetches from BetaSeries even when nothing would
normally trigger a re-fetch (e.g. stats.badges unchanged, or a past month
already cached).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .entity import BetaSeriesEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BetaSeriesConfigEntry, MemberCoordinator, PlanningCoordinator

REFRESH_BADGES_DESCRIPTION = ButtonEntityDescription(
    key="refresh_badges",
    translation_key="refresh_badges",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)

REFRESH_PLANNING_DESCRIPTION = ButtonEntityDescription(
    key="refresh_planning",
    translation_key="refresh_planning",
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
            BetaSeriesRefreshBadgesButton(entry.runtime_data.member, REFRESH_BADGES_DESCRIPTION),
            BetaSeriesRefreshPlanningButton(entry.runtime_data.planning, REFRESH_PLANNING_DESCRIPTION),
        ]
    )


class BetaSeriesRefreshBadgesButton(BetaSeriesEntity, ButtonEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
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
        await self.coordinator.async_force_refresh_badges()


class BetaSeriesRefreshPlanningButton(BetaSeriesEntity, ButtonEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
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
        await self.coordinator.async_force_refresh_planning()
