# ruff: noqa: A005 -- filename mandated by Home Assistant's platform convention
"""Calendar platform for the BetaSeries integration (see CLAUDE.md §4)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEntityDescription, CalendarEvent
from homeassistant.util import dt as dt_util

from .entity import BetaSeriesEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .betaseries import Episode
    from .coordinator import BetaSeriesConfigEntry, PlanningCoordinator

CALENDAR_DESCRIPTION = CalendarEntityDescription(key="release_calendar", translation_key="release_calendar")


async def async_setup_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BetaSeries calendar from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry being set up.
        async_add_entities (AddEntitiesCallback): Callback to register the new entity.

    Returns:
        None: The entity is registered via async_add_entities, nothing is returned.

    """
    async_add_entities([BetaSeriesCalendar(entry.runtime_data.planning, CALENDAR_DESCRIPTION)])


def _to_calendar_event(episode: Episode) -> CalendarEvent:
    """Build an all-day CalendarEvent from a single Episode.

    Args:
        episode (Episode): The episode to represent as a calendar event.

    Returns:
        CalendarEvent: The all-day event for this episode.

    """
    platforms = ", ".join(episode.platforms)
    description_lines = [episode.title]
    # Fall back to the show's synopsis when the episode has none of its own
    # (common for not-yet-aired episodes - see bruno/Planning/member.bru).
    description = episode.description or episode.show.description
    if description:
        description_lines.append(description)
    if platforms:
        description_lines.append(platforms)

    return CalendarEvent(
        start=episode.air_date,
        end=episode.air_date + timedelta(days=1),
        summary=f"{episode.show.title} - {episode.code}",
        description="\n\n".join(description_lines),
        location=episode.resource_url,
        uid=episode.id,
    )


class BetaSeriesCalendar(BetaSeriesEntity, CalendarEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Represent the member's upcoming episodes as calendar events.

    Attributes:
        entity_description (CalendarEntityDescription): Describes this calendar.
        coordinator (PlanningCoordinator): The coordinator providing the planning data.

    """

    entity_description: CalendarEntityDescription  # pyright: ignore[reportIncompatibleVariableOverride]
    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event.

        The coordinator's data is None until its first successful refresh
        (DataUpdateCoordinator types it as _DataT but initializes it to None),
        and the planning is fetched without blocking the entry's setup - see
        __init__.py - so this entity can be added before any planning data
        exists. HA reads this property while adding the entity, hence the
        guard on last_update_success rather than on data itself, which the
        type checker believes can never be None.

        Returns:
            CalendarEvent | None: The earliest unseen episode, or None if there is none.

        """
        if not self.coordinator.last_update_success:
            return None
        for episode in self.coordinator.data:
            if not episode.seen:
                return _to_calendar_event(episode)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range.

        Includes both seen and unseen episodes, unlike the `event` property
        (which only surfaces the next unseen one).

        Both bounds are converted to local time before being reduced to a
        date: HA passes tz-aware datetimes, usually in UTC, so calling
        .date() on them directly would shift the window by a day for any
        user east of UTC (e.g. local midnight in Paris is 22:00 UTC the
        previous day). Episodes are all-day events dated in the show's
        local calendar, so the comparison must be done in local time too.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            start_date (datetime): Start of the requested range.
            end_date (datetime): End of the requested range.

        Returns:
            list[CalendarEvent]: Events for episodes airing within the range.

        """
        if not self.coordinator.last_update_success:
            return []
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [_to_calendar_event(episode) for episode in self.coordinator.data if start <= episode.air_date <= end]
