"""Binary sensor platform for the BetaSeries integration (see CLAUDE.md §5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import BetaSeriesEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .betaseries import MemberData
    from .coordinator import BetaSeriesConfigEntry


@dataclass(kw_only=True, frozen=True)
class BetaSeriesBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a BetaSeries binary sensor backed by MemberCoordinator data.

    Attributes:
        value_fn (Callable[[MemberData], bool]): Extracts this binary sensor's state.

    """

    value_fn: Callable[[MemberData], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[BetaSeriesBinarySensorEntityDescription, ...] = (
    BetaSeriesBinarySensorEntityDescription(
        key="new_episode_available",
        translation_key="new_episode_available",
        value_fn=lambda data: data.stats.episodes_to_watch > 0,
    ),
    BetaSeriesBinarySensorEntityDescription(
        key="movies_to_watch_available",
        translation_key="movies_to_watch_available",
        value_fn=lambda data: data.stats.movies_to_watch > 0,
    ),
)


async def async_setup_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BetaSeries binary sensors from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry being set up.
        async_add_entities (AddEntitiesCallback): Callback to register the new entities.

    Returns:
        None: Entities are registered via async_add_entities, nothing is returned.

    """
    coordinator = entry.runtime_data.member
    async_add_entities(
        BetaSeriesBinarySensor(coordinator, description) for description in BINARY_SENSOR_DESCRIPTIONS
    )


class BetaSeriesBinarySensor(BetaSeriesEntity, BinarySensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Represent a single BetaSeries availability flag.

    Attributes:
        entity_description (BetaSeriesBinarySensorEntityDescription): Describes this binary sensor.

    """

    entity_description: BetaSeriesBinarySensorEntityDescription  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def is_on(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return whether this binary sensor is on.

        Returns:
            bool: The value extracted from the coordinator's member data.

        """
        return self.entity_description.value_fn(self.coordinator.data)
