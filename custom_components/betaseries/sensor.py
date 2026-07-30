"""Sensor platform for the BetaSeries integration (see CLAUDE.md §5)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.util import dt as dt_util

from .entity import BetaSeriesEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .betaseries import CollectionEpisode, MemberData
    from .coordinator import BetaSeriesConfigEntry, MemberCoordinator, PlanningCoordinator

type StateType = int | float | str | None


def _badges_attributes(data: MemberData) -> dict[str, list[dict[str, str | int | None]]]:
    """Return every earned badge's raw fields, for the "badges" sensor's attributes.

    Args:
        data (MemberData): The coordinator's current member data.

    Returns:
        dict[str, list[dict[str, str | int | None]]]: All badge fields, keyed "badges" (empty list until fetched, see MemberCoordinator).

    """
    return {
        "badges": [
            {
                "id": badge.id,
                "code": badge.code,
                "name": badge.name,
                "description": badge.description,
                "date": badge.date.isoformat(),
                "height": badge.height,
                "width": badge.width,
                "level": badge.level,
            }
            for badge in data.badges
        ]
    }


@dataclass(kw_only=True, frozen=True)
class BetaSeriesSensorEntityDescription(SensorEntityDescription):
    """Describe a BetaSeries sensor backed by MemberCoordinator data.

    Attributes:
        value_fn (Callable[[MemberData], StateType]): Extracts this sensor's value.
        attrs_fn (Callable[[MemberData], dict[str, Any]] | None): Extracts this sensor's extra_state_attributes, if any (None for sensors with no attributes).

    """

    value_fn: Callable[[MemberData], StateType]
    attrs_fn: Callable[[MemberData], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[BetaSeriesSensorEntityDescription, ...] = (
    BetaSeriesSensorEntityDescription(
        key="episodes_to_watch",
        translation_key="episodes_to_watch",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.episodes_to_watch,
    ),
    BetaSeriesSensorEntityDescription(
        key="time_to_spend",
        translation_key="time_to_spend",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.time_to_spend,
    ),
    BetaSeriesSensorEntityDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.progress,
    ),
    BetaSeriesSensorEntityDescription(
        key="shows_to_watch",
        translation_key="shows_to_watch",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.shows_to_watch,
    ),
    BetaSeriesSensorEntityDescription(
        key="movies_to_watch",
        translation_key="movies_to_watch",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.movies_to_watch,
    ),
    BetaSeriesSensorEntityDescription(
        key="shows_current",
        translation_key="shows_current",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.shows_current,
    ),
    BetaSeriesSensorEntityDescription(
        key="badges",
        translation_key="badges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.badges,
        attrs_fn=_badges_attributes,
    ),
    BetaSeriesSensorEntityDescription(
        key="shows",
        translation_key="shows",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.shows,
    ),
    BetaSeriesSensorEntityDescription(
        key="shows_finished",
        translation_key="shows_finished",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.shows_finished,
    ),
    BetaSeriesSensorEntityDescription(
        key="episodes",
        translation_key="episodes",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.stats.episodes,
    ),
    BetaSeriesSensorEntityDescription(
        key="time_on_tv",
        translation_key="time_on_tv",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda data: data.stats.time_on_tv,
    ),
    BetaSeriesSensorEntityDescription(
        key="movies",
        translation_key="movies",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.movies,
    ),
    BetaSeriesSensorEntityDescription(
        key="xp",
        translation_key="xp",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.xp,
    ),
    BetaSeriesSensorEntityDescription(
        key="streak_days",
        translation_key="streak_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.streak_days,
    ),
    BetaSeriesSensorEntityDescription(
        key="member_since_days",
        translation_key="member_since_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.stats.member_since_days,
    ),
    BetaSeriesSensorEntityDescription(
        key="episodes_per_month",
        translation_key="episodes_per_month",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.stats.episodes_per_month,
    ),
    BetaSeriesSensorEntityDescription(
        key="favorite_genre",
        translation_key="favorite_genre",
        value_fn=lambda data: data.stats.favorite_genre,
    ),
)


@dataclass(kw_only=True, frozen=True)
class BetaSeriesPlanningSensorEntityDescription(SensorEntityDescription):
    """Describe a BetaSeries sensor backed by PlanningCoordinator data.

    Attributes:
        value_fn (Callable[[CollectionEpisode], datetime | None]): Extracts this sensor's value.

    """

    value_fn: Callable[[CollectionEpisode], datetime | None]


def _next_episode_air_datetime(episodes: CollectionEpisode) -> datetime | None:
    """Return the air date of the earliest unseen episode as a local midnight datetime.

    Args:
        episodes (CollectionEpisode): The planning, sorted by air_date.

    Returns:
        datetime | None: The next unseen episode's air date at local midnight, or None if there is none.

    """
    for episode in episodes:
        if not episode.seen:
            return dt_util.start_of_local_day(episode.air_date)
    return None


NEXT_EPISODE_DESCRIPTION = BetaSeriesPlanningSensorEntityDescription(
    key="next_episode",
    translation_key="next_episode",
    device_class=SensorDeviceClass.TIMESTAMP,
    value_fn=_next_episode_air_datetime,
)

CALENDAR_EVENT_COUNT_DESCRIPTION = SensorEntityDescription(
    key="calendar_event_count",
    translation_key="calendar_event_count",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)


def _episode_counts_by_month(episodes: CollectionEpisode) -> dict[str, int]:
    """Count episodes per "YYYY-MM" month.

    Args:
        episodes (CollectionEpisode): The planning currently loaded by the coordinator.

    Returns:
        dict[str, int]: Number of episodes for each month present in the planning, sorted by month.

    """
    counts = Counter(episode.air_date.strftime("%Y-%m") for episode in episodes)
    return dict(sorted(counts.items()))


async def async_setup_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BetaSeries sensors from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry being set up.
        async_add_entities (AddEntitiesCallback): Callback to register the new entities.

    Returns:
        None: Entities are registered via async_add_entities, nothing is returned.

    """
    member_coordinator = entry.runtime_data.member
    planning_coordinator = entry.runtime_data.planning
    async_add_entities(
        [
            *(BetaSeriesSensor(member_coordinator, description) for description in SENSOR_DESCRIPTIONS),
            BetaSeriesPlanningSensor(planning_coordinator, NEXT_EPISODE_DESCRIPTION),
            BetaSeriesCalendarEventCountSensor(planning_coordinator, CALENDAR_EVENT_COUNT_DESCRIPTION),
        ]
    )


class BetaSeriesSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Represent a single BetaSeries member statistic.

    Attributes:
        entity_description (BetaSeriesSensorEntityDescription): Describes this sensor.
        coordinator (MemberCoordinator): The coordinator providing the member data.

    """

    entity_description: BetaSeriesSensorEntityDescription  # pyright: ignore[reportIncompatibleVariableOverride]
    coordinator: MemberCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> StateType:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the current value of this sensor.

        Returns:
            StateType: The value extracted from the coordinator's member data.

        """
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return this sensor's extra attributes, if its description defines any.

        Returns:
            dict[str, Any] | None: The attributes extracted from the coordinator's member data, or None.

        """
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class BetaSeriesPlanningSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Represent a single BetaSeries sensor derived from the planning.

    Attributes:
        entity_description (BetaSeriesPlanningSensorEntityDescription): Describes this sensor.
        coordinator (PlanningCoordinator): The coordinator providing the planning data.

    """

    entity_description: BetaSeriesPlanningSensorEntityDescription  # pyright: ignore[reportIncompatibleVariableOverride]
    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> datetime | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the current value of this sensor.

        Returns:
            datetime | None: The value extracted from the coordinator's planning data.

        """
        return self.entity_description.value_fn(self.coordinator.data)


class BetaSeriesCalendarEventCountSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Diagnostic sensor exposing how many calendar events are currently loaded.

    Attributes:
        coordinator (PlanningCoordinator): The coordinator providing the planning data.

    """

    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> int:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the total number of episodes currently loaded in the planning.

        Returns:
            int: The number of events the calendar currently exposes.

        """
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int]:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the event count broken down by month.

        Returns:
            dict[str, int]: Number of episodes per "YYYY-MM" month currently loaded.

        """
        return _episode_counts_by_month(self.coordinator.data)
