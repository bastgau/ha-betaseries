"""Sensor platform for the BetaSeries integration (see CLAUDE.md §5)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
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
    from collections.abc import Callable, Iterable
    from datetime import datetime
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .betaseries import CollectionEpisode, Episode, MemberData, WatchListShow
    from .coordinator import (
        BetaSeriesConfigEntry,
        MemberCoordinator,
        PlanningCoordinator,
        PlanningData,
        WatchListCoordinator,
        WatchListData,
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
        key="shows_not_started",
        translation_key="shows_not_started",
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
        key="shows_in_progress",
        translation_key="shows_in_progress",
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
        key="membership_duration",
        translation_key="membership_duration",
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
    attributes are both derived from that same episode, picked once. The
    callback receives the whole PlanningData rather than just its episodes,
    since picking may need more than the schedule (see _previous_episode_airing).

    Attributes:
        episode_fn (Callable[[PlanningData], Episode | None]): Picks the episode this sensor describes.
        at_end_of_day (bool): Whether to timestamp the air date at 23:59:59 rather than at midnight.

    """

    episode_fn: Callable[[PlanningData], Episode | None]
    at_end_of_day: bool = False


def _best_rated(episodes: Iterable[Episode], ratings: dict[str, float]) -> Episode:
    """Return the episode whose show is rated highest, the greatest id breaking a tie.

    Several episodes routinely share one air date, so both airing sensors need
    the same rule to turn "the episodes of that day" into a single pick -
    otherwise the answer would come down to the order the months happened to
    be fetched in, which is not a decision.

    A show BetaSeries has no rating for reports a mean of 0, so it loses to
    any rated one: "unrated" and "rated zero" are deliberately not told apart.
    Ids are compared as numbers, since they are numeric strings and "999"
    would otherwise beat "1001".

    Args:
        episodes (Iterable[Episode]): The episodes to choose from, never empty.
        ratings (dict[str, float]): Member rating per show id, missing shows counting as 0.

    Returns:
        Episode: The winning episode.

    """
    return max(episodes, key=lambda episode: (ratings.get(episode.show.id, 0.0), int(episode.id)))


def _previous_episode_airing(data: PlanningData) -> Episode | None:
    """Return the most recently aired episode, watched or not.

    The mirror image of _next_episode_airing: neither looks at `seen`, because
    both answer "when did/does an episode of my shows come out". This one
    therefore reads nothing that the planning cache could hold stale.

    Its reach is the planning window's own lower bound (see
    PlanningCoordinator): an episode older than that is simply not loaded, and
    a show followed after a past month was cached will not appear for that
    month, since cached months are never refetched.

    Args:
        data (PlanningData): The planning and its per-show ratings.

    Returns:
        Episode | None: The most recently aired episode, or None if none has aired yet.

    """
    today = dt_util.now().date()
    # The planning is sorted by air_date, so the already-aired episodes are a
    # prefix and the last of them carries the most recent air date.
    aired = [episode for episode in data.episodes if episode.air_date < today]
    if not aired:
        return None
    latest = aired[-1].air_date
    return _best_rated((episode for episode in aired if episode.air_date == latest), data.ratings)


def _next_episode_airing(data: PlanningData) -> Episode | None:
    """Return the next episode due to air, whether or not it has been seen.

    Like _previous_episode_airing, this ignores `seen` entirely: it answers
    "when does the next episode of my shows come out", not "what should I
    watch next", and settles a same-day tie the very same way (see
    _best_rated).

    Today counts as upcoming rather than past, since BetaSeries gives no
    airing time: an episode dated today may well air tonight. It belongs here
    until the day is over, so this sensor and the previous one never point at
    the same episode.

    Args:
        data (PlanningData): The planning and its per-show ratings.

    Returns:
        Episode | None: The first episode airing today or later, or None if there is none.

    """
    today = dt_util.now().date()
    # Sorted by air_date, so the upcoming episodes are a suffix and the first
    # of them carries the earliest air date.
    upcoming = [episode for episode in data.episodes if episode.air_date >= today]
    if not upcoming:
        return None
    earliest = upcoming[0].air_date
    return _best_rated((episode for episode in upcoming if episode.air_date == earliest), data.ratings)


PREVIOUS_EPISODE_AIRING_DESCRIPTION = BetaSeriesPlanningSensorEntityDescription(
    key="previous_episode_airing",
    translation_key="previous_episode_airing",
    device_class=SensorDeviceClass.TIMESTAMP,
    episode_fn=_previous_episode_airing,
)

NEXT_EPISODE_AIRING_DESCRIPTION = BetaSeriesPlanningSensorEntityDescription(
    key="next_episode_airing",
    translation_key="next_episode_airing",
    device_class=SensorDeviceClass.TIMESTAMP,
    episode_fn=_next_episode_airing,
    at_end_of_day=True,
)

WATCH_LIST_DESCRIPTION = SensorEntityDescription(
    key="shows_to_catch_up_on",
    translation_key="shows_to_catch_up_on",
    state_class=SensorStateClass.MEASUREMENT,
)

SUGGESTION_DESCRIPTION = SensorEntityDescription(
    key="suggestion_of_the_day",
    translation_key="suggestion_of_the_day",
)


def _suggestion_of_the_day(data: WatchListData) -> tuple[WatchListShow, Episode] | None:
    """Pick one show to watch today, and the episode to resume it at.

    Deterministic, not random, and that distinction is the whole design. A
    sensor's state has to be reproducible from the data it was built on: a
    fresh draw on every refresh would rewrite history 48 times a day without
    anything having happened, fire any automation watching this entity on pure
    noise, and land on a different show after a restart.

    Each show is scored independently for the day rather than an index being
    drawn from the list, because the list is not stable: `random.choice` picks
    `int(random() * len(seq))`, so a show leaving the watch list - any show,
    not just this one - shifts every index and reshuffles the answer. Scoring
    per show means only the winner's own departure can change the winner.

    The episode's id is part of the score, not just the show's, so that acting
    on the suggestion moves it on: watching the suggested episode changes which
    episode that show is resumed at, which changes its score, which hands the
    day to another show - measured at 95% of the time on a 38-show list, the
    rest being the show legitimately winning again with its next episode. That
    is what makes this a suggestion rather than a playlist, and it costs no
    stored state: "already offered today" is read off the data itself.

    The price is that watching *another* show can move the suggestion too,
    since its score changes as well - measured at 2.9% per viewing on the same
    list, and falling as the list grows (16.7% at 5 shows). Not noise: the
    sensor still only ever changes when something was actually watched, which
    is the promise that matters.

    Shows are drawn from the ones the coordinator holds, so the `shows_limit`
    option bounds the draw as well as the list.

    Args:
        data (WatchListData): The watch list as last fetched.

    Returns:
        tuple[WatchListShow, Episode] | None: The chosen show and its oldest unseen episode, or None if there is nothing to watch.

    """
    day = dt_util.now().date().isoformat()
    # A show whose episodes were all filtered out cannot be resumed, so it is
    # not a candidate - suggesting it would leave the attributes half empty.
    # The endpoint returns each show's unseen episodes oldest first, which is
    # where resuming a show means picking up.
    candidates = [(show, next(iter(show.episodes))) for show in data.shows if len(show.episodes)]
    if not candidates:
        return None
    return max(candidates, key=lambda pair: sha256(f"{day}:{pair[0].id}:{pair[1].id}".encode()).digest())


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
        None

    """
    member_coordinator = entry.runtime_data.member
    planning_coordinator = entry.runtime_data.planning
    watch_list_coordinator = entry.runtime_data.watch_list
    async_add_entities(
        [
            *(BetaSeriesSensor(member_coordinator, description) for description in SENSOR_DESCRIPTIONS),
            BetaSeriesWatchListSensor(watch_list_coordinator, WATCH_LIST_DESCRIPTION),
            BetaSeriesSuggestionSensor(watch_list_coordinator, SUGGESTION_DESCRIPTION),
            BetaSeriesPlanningSensor(planning_coordinator, PREVIOUS_EPISODE_AIRING_DESCRIPTION),
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
        an upcoming release; "previous episode airing" uses midnight, so an
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
        return self.coordinator.data.images.get(episode.show.id, {}).get("poster")

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
            "show_images": self.coordinator.data.images.get(episode.show.id, {}),
            "episode_id": episode.id,
            "show_id": episode.show.id,
            "code": episode.code,
            "season": episode.season,
            "number": episode.number,
            "title": episode.title,
            "description": episode.description,
            "show_title": episode.show.title,
            "show_resource_url": episode.show.resource_url,
            "show_description": episode.show.description,
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
        return len(self.coordinator.data.episodes)

    @property
    def extra_state_attributes(self) -> dict[str, int]:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the event count broken down by month.

        Returns:
            dict[str, int]: Number of episodes per "YYYY-MM" month currently loaded.

        """
        if not self.coordinator.last_update_success:
            return {}
        return _episode_counts_by_month(self.coordinator.data.episodes)


class BetaSeriesWatchListSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """List what the member has left to watch, show by show.

    An entity of its own rather than an attribute of one of the member
    statistics, for three reasons that survive the list itself being kept out
    of the recorder (see below - that used to be the justification, and no
    longer is):

    Its coordinator is not theirs. GET /episodes/list is a separate request on
    its own interval, and the entry deliberately tolerates it failing while
    the member statistics still refresh (see __init__.py). Hanging this off a
    MemberCoordinator entity would force a choice between marking a working
    counter unavailable and serving a stale list beside a fresh one.

    It is the only entity that coordinator feeds, so disabling it removes that
    coordinator's last listener and stops the request altogether
    (DataUpdateCoordinator unschedules its refresh once no listener is left).
    That gives the user a switch over a recurring network call, which merging
    would take away.

    Its population matches no member statistic: the endpoint covers the shows
    with at least one unseen episode, which is neither shows_not_started (shows
    never begun) nor shows_in_progress (shows begun and unfinished).

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
        """Return how many shows still have something left to watch.

        Deliberately the show count rather than the episode count: the latter
        is already what episodes_to_watch reports, from a different endpoint,
        so exposing it here again would give two entities the same number.
        This one is the only place the show count surfaces at all. The episode
        count stays available as the total_episodes attribute.

        Returns:
            int: The endpoint's own count, unaffected by the configured list limits.

        """
        return self.coordinator.data.total_shows

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
            "total_shows": self.coordinator.data.total_shows,
            "total_episodes": self.coordinator.data.total_episodes,
            "shows": [
                {
                    "show_id": show.id,
                    "show_title": show.title,
                    "show_images": self._show_images(show),
                    "episode_remaining": show.remaining,
                    "episodes": [
                        {
                            "id": episode.id,
                            "season": episode.season,
                            "number": episode.number,
                            "code": episode.code,
                            "title": episode.title,
                            "description": episode.description,
                            "air_date": episode.air_date.isoformat(),
                            "platforms": list(episode.platforms),
                            "resource_url": episode.resource_url,
                        }
                        for episode in show.episodes
                    ],
                }
                for show in self.coordinator.data.shows
            ],
        }

    def _show_images(self, show: WatchListShow) -> dict[str, str]:
        """Return a show's artwork.

        Args:
            show (WatchListShow): The show to return the artwork of.

        Returns:
            dict[str, str]: The show's image URLs, possibly just its poster.

        """
        return _watch_list_show_images(self.coordinator.data, show)


class BetaSeriesSuggestionSensor(BetaSeriesEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Name one episode to watch today, drawn once a day from the watch list.

    Answers "what do I put on tonight", which none of the other entities do:
    the two airing sensors report release dates, and the watch list reports
    everything at once, which is a list to scroll rather than a decision.

    The draw is over shows, but what it yields is an episode: a series is
    resumed where it was left off, so picking among a show's unseen episodes
    would sooner or later offer S02E05 to someone who stopped after S02E03.

    See _suggestion_of_the_day for why the pick is a per-show daily score
    rather than a draw, and what makes it move.

    Attributes:
        coordinator (WatchListCoordinator): The coordinator providing the watch list.
        _unrecorded_attributes (frozenset[str]): Attributes too bulky to write to the recorder.

    """

    # Artwork URLs are for rendering a card now, never for looking at history.
    _unrecorded_attributes = frozenset({"show_images"})

    coordinator: WatchListCoordinator  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def _pick(self) -> tuple[WatchListShow, Episode] | None:
        """Return today's show and the episode to resume it at.

        The watch list is fetched without blocking the entry's setup (see
        __init__.py), so this entity can be added before any watch list data
        exists - hence the guard on last_update_success.

        Returns:
            tuple[WatchListShow, Episode] | None: The chosen show and episode, or None if there is nothing to suggest.

        """
        if not self.coordinator.last_update_success:
            return None
        return _suggestion_of_the_day(self.coordinator.data)

    @property
    def native_value(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the episode suggested for today, as "<show> - <code>".

        An episode rather than just the show, because the show alone does not
        answer the question: on a series you are part-way through, "watch
        Black Mirror" still leaves you looking up where you stopped.

        The three parts together are what a notification or a card can show
        unaided. The episode's own title is dropped when the API has none,
        rather than leaving a dangling separator. Measured at 73 characters at
        worst on a real account, well inside the 255 a state may hold.

        Returns:
            str | None: The episode designation, or None when there is nothing left to watch.

        """
        pick = self._pick
        if pick is None:
            return None
        show, episode = pick
        designation = f"{show.title} {episode.code}"
        return f"{designation} : {episode.title}" if episode.title else designation

    @property
    def entity_picture(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the suggested show's poster.

        Returns:
            str | None: The poster URL, or None if there is no suggestion or no poster.

        """
        pick = self._pick
        if pick is None:
            return None
        return _watch_list_show_images(self.coordinator.data, pick[0]).get("poster")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the suggested episode's identifiers and details.

        Mirrors what the two airing sensors expose, so a card written for one
        works for this one, plus `episode_remaining` - how much of the show is
        left, which is what makes a suggestion worth taking or skipping.

        Returns:
            dict[str, Any] | None: The suggestion's attributes, or None when there is nothing to suggest.

        """
        pick = self._pick
        if pick is None:
            return None
        show, episode = pick
        return {
            "show_images": _watch_list_show_images(self.coordinator.data, show),
            "episode_id": episode.id,
            "show_id": show.id,
            "code": episode.code,
            "season": episode.season,
            "number": episode.number,
            "title": episode.title,
            "description": episode.description,
            "show_title": show.title,
            "air_date": episode.air_date.isoformat(),
            "episode_remaining": show.remaining,
            "platforms": list(episode.platforms),
            "resource_url": episode.resource_url,
        }


def _watch_list_show_images(data: WatchListData, show: WatchListShow) -> dict[str, str]:
    """Return a show's artwork, falling back to the poster the list itself carries.

    GET /shows/display gives every artwork kind but is only fetched for shows
    not already cached; GET /episodes/list always carries a poster, so it
    covers the gap when the images call failed.

    Args:
        data (WatchListData): The watch list as last fetched, holding the cached artwork.
        show (WatchListShow): The show to return the artwork of.

    Returns:
        dict[str, str]: The show's image URLs, possibly just its poster.

    """
    images = data.images.get(show.id, {})
    if images:
        return images
    return {"poster": show.poster} if show.poster else {}
