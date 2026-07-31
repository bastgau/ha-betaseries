"""Sensor platform for the BetaSeries integration (see CLAUDE.md §5)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
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

    from .betaseries import CollectionEpisode, Episode, MemberData, WatchListShow
    from .coordinator import (
        BetaSeriesConfigEntry,
        MemberCoordinator,
        PlanningCoordinator,
        WatchListCoordinator,
    )

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
    """Describe a BetaSeries sensor backed by a single episode of the planning.

    These sensors only differ by which episode they single out, so they share
    one selection callback: the state (its air date) and the actionable
    attributes are both derived from that same episode, picked once.

    Attributes:
        episode_fn (Callable[[CollectionEpisode], Episode | None]): Picks the episode this sensor describes.
        at_end_of_day (bool): Whether to timestamp the air date at 23:59:59 rather than at midnight.

    """

    episode_fn: Callable[[CollectionEpisode], Episode | None]
    at_end_of_day: bool = False


def _latest_unwatched_episode(episodes: CollectionEpisode) -> Episode | None:
    """Return the most recently aired episode the member has not watched yet.

    Walks the planning backwards (it is sorted by air_date): the newest unseen
    episode is the one to act on - the one just aired or about to be watched.
    Deliberately not the oldest unseen one, which on a large backlog would be
    a months-old straggler that never changes.

    Episodes airing today or later are skipped: the planning window extends
    months into the future (see PlanningCoordinator), and those episodes are
    unseen simply because they do not exist yet - they say nothing about what
    the member has left to watch. Today is excluded too, since BetaSeries
    gives no airing time: an episode dated today may well air tonight. It
    belongs to the "next episode airing" sensor until the day is over, so
    the two sensors never point at the same episode.

    Args:
        episodes (CollectionEpisode): The planning, sorted by air_date.

    Returns:
        Episode | None: The newest already-aired unseen episode, or None if there is none.

    """
    today = dt_util.now().date()
    return next(
        (episode for episode in reversed(tuple(episodes)) if not episode.seen and episode.air_date < today),
        None,
    )


def _next_episode_airing(episodes: CollectionEpisode) -> Episode | None:
    """Return the next episode due to air, whether or not it has been seen.

    Unlike _latest_unwatched_episode, this ignores `seen` entirely: it answers
    "when does the next episode of my shows come out", not "what should I
    watch next".

    Args:
        episodes (CollectionEpisode): The planning, sorted by air_date.

    Returns:
        Episode | None: The first episode airing today or later, or None if there is none.

    """
    today = dt_util.now().date()
    return next((episode for episode in episodes if episode.air_date >= today), None)


LATEST_UNWATCHED_EPISODE_DESCRIPTION = BetaSeriesPlanningSensorEntityDescription(
    key="latest_unwatched_episode",
    translation_key="latest_unwatched_episode",
    device_class=SensorDeviceClass.TIMESTAMP,
    episode_fn=_latest_unwatched_episode,
)

NEXT_EPISODE_AIRING_DESCRIPTION = BetaSeriesPlanningSensorEntityDescription(
    key="next_episode_airing",
    translation_key="next_episode_airing",
    device_class=SensorDeviceClass.TIMESTAMP,
    episode_fn=_next_episode_airing,
    at_end_of_day=True,
)

WATCH_LIST_DESCRIPTION = SensorEntityDescription(
    key="watch_list",
    translation_key="watch_list",
    state_class=SensorStateClass.MEASUREMENT,
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
    watch_list_coordinator = entry.runtime_data.watch_list
    async_add_entities(
        [
            *(BetaSeriesSensor(member_coordinator, description) for description in SENSOR_DESCRIPTIONS),
            BetaSeriesWatchListSensor(watch_list_coordinator, WATCH_LIST_DESCRIPTION),
            BetaSeriesPlanningSensor(planning_coordinator, LATEST_UNWATCHED_EPISODE_DESCRIPTION),
            BetaSeriesPlanningSensor(planning_coordinator, NEXT_EPISODE_AIRING_DESCRIPTION),
            BetaSeriesCalendarEventCountSensor(planning_coordinator, CALENDAR_EVENT_COUNT_DESCRIPTION),
        ]
    )


class BetaSeriesSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Represent a single BetaSeries member statistic.

    Attributes:
        entity_description (BetaSeriesSensorEntityDescription): Describes this sensor.
        coordinator (MemberCoordinator): The coordinator providing the member data.
        _unrecorded_attributes (frozenset[str]): Attributes too bulky to write to the recorder.

    """

    # "badges" is the only bulky attribute any of these sensors carries - one
    # entry per badge ever earned, measured at ~10 kB for 40 badges. Declared
    # on the shared class since the other statistics have no attribute by that
    # name, so nothing else is affected. See BetaSeriesWatchListSensor for why
    # these are kept out of the recorder.
    _unrecorded_attributes = frozenset({"badges"})

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
        _unrecorded_attributes (frozenset[str]): Attributes too bulky to write to the recorder.

    """

    # Artwork URLs are for rendering a card now, never for looking at history:
    # what mattered about a past state is which episode it pointed at, and the
    # identifiers below carry that. See BetaSeriesWatchListSensor.
    _unrecorded_attributes = frozenset({"show_images"})

    entity_description: BetaSeriesPlanningSensorEntityDescription  # pyright: ignore[reportIncompatibleVariableOverride]
    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def _episode(self) -> Episode | None:
        """Return the episode this sensor currently describes.

        The planning is fetched without blocking the entry's setup (see
        __init__.py), so this entity can be added before any planning data
        exists - guard on last_update_success, since the coordinator's data
        is still None at that point (see BetaSeriesCalendar.event).

        Returns:
            Episode | None: The selected episode, or None if there is none (or no data yet).

        """
        if not self.coordinator.last_update_success:
            return None
        return self.entity_description.episode_fn(self.coordinator.data)

    @property
    def native_value(self) -> datetime | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the selected episode's air date, as a local timestamp.

        BetaSeries only ever gives the day an episode airs, never the time,
        so the hour here is picked rather than known - each sensor pins it to
        the end of the day it can never be wrong about, which keeps the
        frontend's relative rendering ("in 3 days", "2 days ago") consistent
        with what the sensor claims to be. "Next episode airing" uses
        23:59:59, so an episode airing today stays in the future all day
        instead of reading "6 hours ago" at 06:00 under a sensor announcing
        an upcoming release; "latest unwatched episode" uses midnight, so an
        already-aired episode always reads in the past.

        Returns:
            datetime | None: The episode's air date as a timestamp, or None if there is no episode.

        """
        episode = self._episode
        if episode is None:
            return None
        start_of_day = dt_util.start_of_local_day(episode.air_date)
        if not self.entity_description.at_end_of_day:
            return start_of_day
        return start_of_day + timedelta(days=1) - timedelta(seconds=1)

    @property
    def entity_picture(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the poster of the show the selected episode belongs to.

        Posters come from the coordinator's bulk /shows/display cache and are
        public URLs on pictures.betaseries.com, loadable by the frontend with
        no authentication. Shows without a poster simply have no entry there,
        so this returns None rather than a broken image - BetaSeries' episode
        thumbnail endpoint is not a usable fallback (see CLAUDE.md §4).

        Returns:
            str | None: The show's poster URL, or None if there is no episode or no poster.

        """
        episode = self._episode
        if episode is None:
            return None
        return self.coordinator.show_images.get(episode.show.id, {}).get("poster")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the selected episode's identifiers and details.

        These make the sensor actionable from a dashboard card: episode_id
        and show_id are what the (v3) services target, and Home Assistant's
        CalendarEvent has no field to carry them, so the calendar entity
        cannot expose them (see CLAUDE.md §5).

        Returns:
            dict[str, Any] | None: The episode's attributes, or None if there is no episode.

        """
        episode = self._episode
        if episode is None:
            return None
        return {
            # Every artwork the show has (poster/banner/box/show/clearlogo),
            # so a card can pick a different one than entity_picture's poster -
            # a banner for a wide card, a clearlogo to overlay, ... Kinds the
            # show has no image for are absent rather than null.
            "show_images": self.coordinator.show_images.get(episode.show.id, {}),
            "episode_id": episode.id,
            "show_id": episode.show.id,
            "code": episode.code,
            "season": episode.season,
            "number": episode.number,
            "title": episode.title,
            "show_title": episode.show.title,
            "platforms": list(episode.platforms),
            "resource_url": episode.resource_url,
        }


class BetaSeriesCalendarEventCountSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Diagnostic sensor exposing how many calendar events are currently loaded.

    Attributes:
        coordinator (PlanningCoordinator): The coordinator providing the planning data.

    """

    coordinator: PlanningCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> int | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the total number of episodes currently loaded in the planning.

        Returns:
            int | None: The number of events the calendar currently exposes, or None before the first successful refresh.

        """
        if not self.coordinator.last_update_success:
            return None
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int]:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the event count broken down by month.

        Returns:
            dict[str, int]: Number of episodes per "YYYY-MM" month currently loaded.

        """
        if not self.coordinator.last_update_success:
            return {}
        return _episode_counts_by_month(self.coordinator.data)


class BetaSeriesWatchListSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """List what the member has left to watch, show by show.

    Kept apart from the episodes_to_watch / shows_to_watch statistics
    sensors, which it would otherwise saddle with a bulky attribute: those
    two only ever hold a number, so this list weighing on nothing but its own
    entity leaves the plain counters untouched.

    Attributes:
        coordinator (WatchListCoordinator): The coordinator providing the watch list.
        _unrecorded_attributes (frozenset[str]): Attributes too bulky to write to the recorder.

    """

    # The whole point of this entity is a list rebuilt from scratch on every
    # refresh, so recording it would write kilobytes per state change to
    # describe a state that only ever means "here is the list right now".
    # Measured at ~8.5 kB with the default limits, against ~50 bytes for
    # everything else this entity carries - and the recorder drops *all* of an
    # entity's attributes past 16 kB (MAX_STATE_ATTRS_BYTES), which the
    # shows_limit option alone can reach. The state and the two counters stay
    # recorded, so history keeps the numbers worth graphing.
    #
    # This only governs what is written to the database: cards, templates and
    # automations still read the full attribute from the live state.
    _unrecorded_attributes = frozenset({"shows"})

    coordinator: WatchListCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> int:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return how many episodes are left to watch, across every show.

        Returns:
            int: The endpoint's own count, unaffected by the configured list limits.

        """
        return self.coordinator.total_episodes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the totals, and the first few shows with their next episodes.

        How many shows and episodes appear here is set by the shows_limit /
        episodes_limit options; the two totals are the endpoint's own and
        ignore them. Empty until the watch list has been fetched successfully.

        Returns:
            dict[str, Any]: The totals to watch, plus the listed shows.

        """
        if not self.coordinator.last_update_success:
            return {"total_shows": 0, "total_episodes": 0, "shows": []}
        return {
            "total_shows": self.coordinator.total_shows,
            "total_episodes": self.coordinator.total_episodes,
            "shows": [
                {
                    "show_id": show.id,
                    "show_title": show.title,
                    "show_images": self._show_images(show),
                    "episode_remaining": show.remaining,
                    "episodes": [
                        {
                            "id": episode.id,
                            "code": episode.code,
                            "title": episode.title,
                            "air_date": episode.air_date.isoformat(),
                            "platforms": list(episode.platforms),
                            "resource_url": episode.resource_url,
                        }
                        for episode in show.episodes
                    ],
                }
                for show in self.coordinator.data
            ],
        }

    def _show_images(self, show: WatchListShow) -> dict[str, str]:
        """Return a show's artwork, falling back to the poster the list itself carries.

        GET /shows/display gives every artwork kind but is only fetched for
        shows not already cached; GET /episodes/list always carries a poster,
        so it covers the gap when the images call failed.

        Args:
            show (WatchListShow): The show to return the artwork of.

        Returns:
            dict[str, str]: The show's image URLs, possibly just its poster.

        """
        images = self.coordinator.show_images.get(show.id, {})
        if images:
            return images
        return {"poster": show.poster} if show.poster else {}
