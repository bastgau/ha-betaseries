"""Data update coordinator for the BetaSeries integration."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .betaseries import AuthError, Badge, CollectionBadge, CollectionEpisode, Episode, Error, Show, ShowImages
from .const import (
    BADGES_STORE_KEY_PREFIX,
    BADGES_STORE_VERSION,
    CONF_EPISODES_LIMIT,
    CONF_EPISODES_SCAN_INTERVAL,
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    CONF_SHOWS_LIMIT,
    DEFAULT_EPISODES_LIMIT,
    DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES,
    DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES,
    DEFAULT_PLANNING_MONTHS_AHEAD,
    DEFAULT_PLANNING_MONTHS_BEHIND,
    DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES,
    DEFAULT_SHOWS_LIMIT,
    DOMAIN,
    EPISODE_SHOW_IMAGES_STORE_KEY_PREFIX,
    EPISODE_SHOW_IMAGES_STORE_VERSION,
    PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX,
    PLANNING_SHOW_IMAGES_STORE_VERSION,
    PLANNING_STORE_KEY_PREFIX,
    PLANNING_STORE_VERSION,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .betaseries import Client, CollectionWatchListShow, MemberData

_LOGGER = logging.getLogger(__name__)

type BetaSeriesConfigEntry = ConfigEntry["BetaSeriesData"]


def _compact(text: str | None) -> str | None:
    """Collapse a (possibly multi-line, pretty-printed) string to a single line for logging.

    Args:
        text (str | None): The text to compact, or None.

    Returns:
        str | None: `text` with every run of whitespace collapsed to a single space, or None if `text` is None.

    """
    return " ".join(text.split()) if text is not None else None


def _log_auth_failure(title: str, err: AuthError) -> None:
    """Log the BetaSeries error that rejected the stored credentials, prompting reauthentication.

    The client itself does no logging (see AuthError's docstring), so the
    response status/body it carries is only ever surfaced here, on the HA
    side - this stays true regardless of how the client is packaged
    (bundled sub-package today, an external library if extracted later).

    BetaSeries does not support regenerating just the API secret for an
    existing application - if the api_key/client_secret themselves are no
    longer valid (not just the access token), the user must create a new
    application on betaseries.com and reauthenticate with it.

    Args:
        title (str): The config entry's title, to identify which account failed.
        err (AuthError): The error raised by the client, carrying the response's status/body.

    Returns:
        None: This only logs; nothing is returned.

    """
    _LOGGER.warning(
        "BetaSeries rejected the stored credentials for %s (HTTP %s): %s. A reauthentication "
        "will be requested. If reauthenticating does not resolve this, the API key/secret "
        "themselves may no longer be valid - BetaSeries does not support regenerating just "
        "the secret, a new application must be created on betaseries.com",
        title,
        err.status,
        _compact(err.body),
    )


class _CacheStore[DataT: dict[str, Any]](Store[DataT]):
    """Store for a pure cache, discarding old data on a version bump.

    Every Store in this integration only ever holds a performance
    optimization (avoid re-fetching badge details whose count hasn't changed,
    or past planning months that can no longer change - see MemberCoordinator
    and PlanningCoordinator). Starting empty is therefore always safe and
    cheap: the owning coordinator just refetches as if nothing had been
    cached, instead of this class carrying a real migration for each past
    schema change.

    Bump the matching *_STORE_VERSION in const.py whenever a cached shape
    changes, so stale entries are dropped rather than deserialized wrongly.

    """

    async def async_load(self) -> DataT | None:
        """Load the cache, discarding it outright if its version is unreadable.

        Store raises UnsupportedStorageVersionError - before ever calling
        _async_migrate_func - when the file on disk has a *newer* major
        version than this class expects, which happens whenever the
        integration is downgraded to a release that used an older cache
        shape. Since these stores only hold a rebuildable cache, dropping
        the file is always preferable to failing the whole setup.

        Returns:
            DataT | None: The cached data, or None when there is none (or it was discarded).

        """
        try:
            return await super().async_load()
        except UnsupportedStorageVersionError as err:
            _LOGGER.warning(
                "Discarding the %s cache: it was written by a newer version of the integration "
                "(storage version %s, this version reads up to %s). It will be rebuilt on the "
                "next refresh; nothing is lost, these files only ever hold cached API responses",
                self.key,
                err.found_version,
                err.max_supported_version,
            )
            await self.async_remove()
            return None

    async def _async_migrate_func(  # pylint: disable=unused-argument
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> DataT:
        """Discard any data from a previous store version.

        Args:
            old_major_version (int): Unused; any past version is discarded the same way.
            old_minor_version (int): Unused; any past version is discarded the same way.
            old_data (dict[str, Any]): Unused; the previous shape of the cached data.

        Returns:
            DataT: An empty cache, forcing a full refetch.

        """
        return cast("DataT", {})


def _images_to_dict(images: ShowImages) -> dict[str, str]:
    """Serialize a show's image URLs, dropping the ones it doesn't have.

    Any field of ShowImages may be None (a show can have no artwork at all),
    and those are left out entirely rather than stored/exposed as null: what
    remains is exactly what a dashboard card can actually display.

    Args:
        images (ShowImages): The show's image URLs, as returned by GET /shows/display.

    Returns:
        dict[str, str]: The URLs the show actually has, keyed by image kind.

    """
    return {
        kind: url
        for kind, url in (
            ("show", images.show),
            ("banner", images.banner),
            ("box", images.box),
            ("poster", images.poster),
            ("clearlogo", images.clearlogo),
        )
        if url
    }


async def _async_get_show_images(
    client: Client,
    store: Store[dict[str, Any]],
    show_ids: frozenset[str],
    title: str,
) -> dict[str, dict[str, str]]:
    """Return each show's image URLs, fetching only the ones not already cached.

    Shared by the coordinators that display shows: a show's images essentially
    never change, so cached ones are never refetched; shows no longer in the
    caller's set are dropped so the cache doesn't grow unbounded. Shows that
    have no image at all are cached as an empty dict, which stops them being
    refetched on every refresh.

    Failures are swallowed on purpose: these images are decoration, and the
    caller's own data refreshed fine by the time this runs - failing the whole
    update over a missing image would take its entities down with it.

    Args:
        client (Client): The BetaSeries API client used to fetch the shows.
        store (Store[dict[str, Any]]): The caller's own persisted image cache.
        show_ids (frozenset[str]): Show ids the caller currently displays.
        title (str): The config entry's title, for logging.

    Returns:
        dict[str, dict[str, str]]: Image URLs per show id, each without its unset entries.

    """
    stored: dict[str, Any] = await store.async_load() or {}
    cached: dict[str, dict[str, str]] = {show_id: stored[show_id] for show_id in show_ids if show_id in stored}
    missing = show_ids - cached.keys()

    if missing:
        try:
            _LOGGER.debug("Fetching images for %s new show(s) of %s from BetaSeries", len(missing), title)
            shows = await client.fetch_shows(sorted(missing))
        except Error as err:
            _LOGGER.debug("Fetching show images for %s failed (HTTP %s): %s", title, err.status, _compact(err.body))
        else:
            for show_id in missing:
                show = shows.for_show(show_id)
                information = show.additional_information if show is not None else None
                cached[show_id] = _images_to_dict(information.images) if information is not None else {}

    if cached != stored:
        # Either new images were fetched, or shows left the caller's set and
        # their entries were dropped by the comprehension above.
        await store.async_save(cached)

    return cached


def _badge_to_dict(badge: Badge) -> dict[str, Any]:
    """Serialize a Badge for storage (date -> ISO string).

    Args:
        badge (Badge): The badge to serialize.

    Returns:
        dict[str, Any]: A JSON-serializable representation of the badge.

    """
    return {
        "id": badge.id,
        "code": badge.code,
        "name": badge.name,
        "description": badge.description,
        "date": badge.date.isoformat(),
        "height": badge.height,
        "width": badge.width,
        "level": badge.level,
    }


def _badge_from_dict(data: dict[str, Any]) -> Badge:
    """Deserialize a Badge from storage (ISO string -> datetime).

    Args:
        data (dict[str, Any]): The stored representation of the badge.

    Returns:
        Badge: The deserialized badge.

    """
    return Badge(
        id=data["id"],
        code=data["code"],
        name=data["name"],
        description=data["description"],
        date=datetime.fromisoformat(data["date"]),
        height=data["height"],
        width=data["width"],
        level=data["level"],
    )


class MemberCoordinator(DataUpdateCoordinator["MemberData"]):
    """Fetch member data and statistics via Client.fetch_member_data() (see CLAUDE.md §5).

    Badge details (MemberData.badges) are only refetched (GET /members/badges)
    when stats.badges - the count already included in fetch_member_data() -
    differs from the last known count, persisted in a Store alongside the
    badge list itself so a HA restart doesn't force a refetch when nothing
    changed. The client has no state of its own to make that call, so this
    coordinator orchestrates it, the same way PlanningCoordinator decides
    which planning months need fetching.

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch member data.
        badges_store (Store[dict[str, Any]]): Persisted cache of the last known badge count/details.

    """

    config_entry: BetaSeriesConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BetaSeriesConfigEntry, client: Client) -> None:
        """Initialize the coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
            client (Client): The BetaSeries API client used to fetch member data.

        """
        scan_interval_minutes = config_entry.options.get(
            CONF_MEMBER_SCAN_INTERVAL, DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client
        self.badges_store: Store[dict[str, Any]] = _CacheStore[dict[str, Any]](
            hass, BADGES_STORE_VERSION, f"{BADGES_STORE_KEY_PREFIX}_{config_entry.entry_id}"
        )

    async def _async_update_data(self) -> MemberData:
        """Fetch the latest member data, refetching badge details only if their count changed.

        Returns:
            MemberData: The member's id, login, xp, viewing statistics and badges.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        try:
            _LOGGER.debug("Fetching member data for %s from BetaSeries", self.config_entry.title)
            member_data = await self.client.fetch_member_data()
            badges = await self._async_get_badges(member_data.identity.id, member_data.stats.badges)
        except AuthError as err:
            _log_auth_failure(self.config_entry.title, err)
            raise ConfigEntryAuthFailed from err
        except Error as err:
            _LOGGER.debug(
                "Fetching member data for %s failed (HTTP %s): %s",
                self.config_entry.title,
                err.status,
                _compact(err.body),
            )
            raise UpdateFailed(str(err)) from err

        return dataclasses.replace(member_data, badges=badges)

    async def _async_get_badges(self, member_id: str, badge_count: int) -> CollectionBadge:
        """Return the member's badges, refetching them only if their count changed.

        Errors from fetching the badges propagate to the caller unchanged.

        Args:
            member_id (str): BetaSeries member id to fetch badges for.
            badge_count (int): The current badge count, from stats.badges.

        Returns:
            CollectionBadge: The member's badges, freshly fetched or from cache.

        """
        stored = await self.badges_store.async_load()

        if stored is not None and stored.get("count") == badge_count:
            return CollectionBadge(tuple(_badge_from_dict(data) for data in stored["badges"]))

        _LOGGER.debug("Badge count changed for %s, fetching badge details from BetaSeries", self.config_entry.title)
        badges = await self.client.fetch_badges(member_id)
        await self.badges_store.async_save(
            {"count": badge_count, "badges": [_badge_to_dict(badge) for badge in badges]}
        )
        return badges

    async def async_clean_badges_cache(self) -> None:
        """Force a full refetch of badge details on the next refresh, then refresh now.

        Clears the badges_store cache first: _async_get_badges() only skips
        re-fetching when the cached count matches stats.badges, so without
        this, pressing the "Clean badges cache" button would silently do nothing
        if the count hadn't changed (e.g. a badge's description changed
        without a new badge being earned).

        Returns:
            None: The coordinator's data is updated in place, like any refresh.

        """
        _LOGGER.debug("Clearing cached badges for %s, forcing a full refetch", self.config_entry.title)
        await self.badges_store.async_remove()
        await self.async_refresh()


class PlanningCoordinator(DataUpdateCoordinator[CollectionEpisode]):
    """Fetch the member's planning via Client.fetch_planning() (see CLAUDE.md §4).

    Past months are fetched once and cached in a Store (they never change
    once the month is over), so regular refreshes only re-fetch the current
    and future months. If the configured months_behind grows, the missing
    older months are fetched and added to the cache.

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch the planning.
        planning_store (Store[dict[str, list[dict[str, Any]]]]): Persisted cache of past months' episodes.
        show_images_store (Store[dict[str, Any]]): Persisted cache of each show's image URLs.
        show_images (dict[str, dict[str, str]]): Image URLs per show id currently in the window, empty dicts included.

    """

    config_entry: BetaSeriesConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BetaSeriesConfigEntry, client: Client) -> None:
        """Initialize the coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
            client (Client): The BetaSeries API client used to fetch the planning.

        """
        scan_interval_minutes = config_entry.options.get(
            CONF_PLANNING_SCAN_INTERVAL, DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_planning",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client
        self.planning_store: Store[dict[str, list[dict[str, Any]]]] = _CacheStore[dict[str, list[dict[str, Any]]]](
            hass, PLANNING_STORE_VERSION, f"{PLANNING_STORE_KEY_PREFIX}_{config_entry.entry_id}"
        )
        self.show_images_store: Store[dict[str, Any]] = _CacheStore[dict[str, Any]](
            hass, PLANNING_SHOW_IMAGES_STORE_VERSION, f"{PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX}_{config_entry.entry_id}"
        )
        self.show_images: dict[str, dict[str, str]] = {}

    async def _async_update_data(self) -> CollectionEpisode:
        """Fetch the current/future planning and merge it with the cached past months.

        Returns:
            CollectionEpisode: The member's episodes, sorted by air_date.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        # NumberSelector-backed options always come back as float (see config_flow.py),
        # but range()/list indexing below require int.
        months_ahead = int(self.config_entry.options.get(CONF_PLANNING_MONTHS_AHEAD, DEFAULT_PLANNING_MONTHS_AHEAD))
        months_behind = int(self.config_entry.options.get(CONF_PLANNING_MONTHS_BEHIND, DEFAULT_PLANNING_MONTHS_BEHIND))
        today = dt_util.now().date()

        try:
            past_by_month = await self._async_get_cached_past_months(_past_months(today, months_behind))
            current_and_future = [
                await self._async_fetch_planning(month) for month in _upcoming_months(today, months_ahead)
            ]
        except AuthError as err:
            _log_auth_failure(self.config_entry.title, err)
            raise ConfigEntryAuthFailed from err
        except Error as err:
            _LOGGER.debug(
                "Fetching planning for %s failed (HTTP %s): %s",
                self.config_entry.title,
                err.status,
                _compact(err.body),
            )
            raise UpdateFailed(str(err)) from err

        episodes = (episode for episodes in (*past_by_month.values(), *current_and_future) for episode in episodes)
        planning = CollectionEpisode(tuple(sorted(episodes, key=lambda episode: episode.air_date)))
        self.show_images = await _async_get_show_images(
            self.client, self.show_images_store, planning.show_ids, self.config_entry.title
        )
        return planning

    async def async_clean_planning_cache(self) -> None:
        """Force a full refetch of every month, including cached past ones, then refresh now.

        Clears both stores first: _async_get_cached_past_months() and
        _async_get_show_images() only fetch what is missing from their cache, so
        without this, past months (which never change once over) and already
        known show images would keep being served from the store untouched by the
        "Clean planning cache" button.

        Returns:
            None: The coordinator's data is updated in place, like any refresh.

        """
        _LOGGER.debug("Clearing cached past months for %s, forcing a full refetch", self.config_entry.title)
        await self.planning_store.async_remove()
        await self.show_images_store.async_remove()
        await self.async_refresh()

    async def _async_fetch_planning(self, month: str) -> CollectionEpisode:
        """Fetch a single month's planning, logging the account name beforehand.

        Errors from the underlying request propagate to the caller unchanged.

        Args:
            month (str): Month to fetch, as "YYYY-MM".

        Returns:
            CollectionEpisode: The member's episodes for that month.

        """
        _LOGGER.debug("Fetching planning for %s (month=%s) from BetaSeries", self.config_entry.title, month)
        return await self.client.fetch_planning(month)

    async def _async_get_cached_past_months(self, months: list[str]) -> dict[str, tuple[Episode, ...]]:
        """Return past months' episodes, fetching and caching any that are missing.

        Errors from fetching a missing month propagate to the caller unchanged.

        Args:
            months (list[str]): Past "YYYY-MM" months that should be in the cache.

        Returns:
            dict[str, tuple[Episode, ...]]: Episodes for each requested month.

        """
        stored = await self.planning_store.async_load() or {}
        stale = [month for month in stored if month not in months]
        missing = [month for month in months if month not in stored]

        for month in stale:
            # No longer within months_behind: drop it so the store doesn't grow
            # unbounded as time passes and the configured window slides forward.
            del stored[month]

        for month in missing:
            episodes = await self._async_fetch_planning(month)
            stored[month] = [_episode_to_dict(episode) for episode in episodes]

        if stale or missing:
            await self.planning_store.async_save(stored)

        return {month: tuple(_episode_from_dict(data) for data in stored[month]) for month in months}


def _episode_to_dict(episode: Episode) -> dict[str, Any]:
    """Serialize an Episode for storage (date -> ISO string, show flattened to id/title).

    show.additional_information/episodes are never persisted here: they are
    only ever populated on demand via Episode.fetch_show()/Show.fetch_episodes(),
    not by this planning cache.

    Args:
        episode (Episode): The episode to serialize.

    Returns:
        dict[str, Any]: A JSON-serializable representation of the episode.

    """
    return {
        "id": episode.id,
        "season": episode.season,
        "number": episode.number,
        "code": episode.code,
        "title": episode.title,
        "description": episode.description,
        "air_date": episode.air_date.isoformat(),
        "seen": episode.seen,
        "platforms": episode.platforms,
        "resource_url": episode.resource_url,
        "show_id": episode.show.id,
        "show_title": episode.show.title,
        "show_description": episode.show.description,
        "show_slug": episode.show.slug,
    }


def _episode_from_dict(data: dict[str, Any]) -> Episode:
    """Deserialize an Episode from storage (ISO string -> date).

    Args:
        data (dict[str, Any]): The stored representation of the episode.

    Returns:
        Episode: The deserialized episode.

    """
    return Episode(
        id=data["id"],
        season=data["season"],
        number=data["number"],
        code=data["code"],
        title=data["title"],
        description=data["description"],
        air_date=date.fromisoformat(data["air_date"]),
        seen=data["seen"],
        platforms=tuple(data["platforms"]),
        resource_url=data["resource_url"],
        show=Show(
            id=data["show_id"],
            title=data["show_title"],
            description=data["show_description"],
            slug=data["show_slug"],
        ),
    )


class EpisodeCoordinator(DataUpdateCoordinator["CollectionWatchListShow"]):
    """Fetch the shows still to watch via Client.fetch_watch_list() (GET /episodes/list).

    Kept apart from PlanningCoordinator rather than derived from it: the
    planning is bounded by its month window, so a show whose last unseen
    episode aired before that window would silently drop out of the watch
    list. This endpoint also carries each show's `remaining` count and the
    global totals, which the planning has no equivalent for.

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch the watch list.
        show_images_store (Store[dict[str, Any]]): Persisted cache of each listed show's image URLs.
        show_images (dict[str, dict[str, str]]): Image URLs per listed show id.
        total_shows (int): Shows with at least one unseen episode, ignoring the configured limits.
        total_episodes (int): Unseen episodes across every show, ignoring the configured limits.

    """

    config_entry: BetaSeriesConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: BetaSeriesConfigEntry, client: Client) -> None:
        """Initialize the coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
            client (Client): The BetaSeries API client used to fetch the watch list.

        """
        scan_interval_minutes = config_entry.options.get(
            CONF_EPISODES_SCAN_INTERVAL, DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_episodes",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client
        self.show_images_store: Store[dict[str, Any]] = _CacheStore[dict[str, Any]](
            hass, EPISODE_SHOW_IMAGES_STORE_VERSION, f"{EPISODE_SHOW_IMAGES_STORE_KEY_PREFIX}_{config_entry.entry_id}"
        )
        self.show_images: dict[str, dict[str, str]] = {}
        self.total_shows = 0
        self.total_episodes = 0

    async def _async_update_data(self) -> CollectionWatchListShow:
        """Fetch the shows still to watch, capped by the configured limits.

        Returns:
            CollectionWatchListShow: The listed shows with their unseen episodes, plus the global counters.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        # NumberSelector-backed options always come back as float (see config_flow.py).
        shows_limit = int(self.config_entry.options.get(CONF_SHOWS_LIMIT, DEFAULT_SHOWS_LIMIT))
        episodes_limit = int(self.config_entry.options.get(CONF_EPISODES_LIMIT, DEFAULT_EPISODES_LIMIT))

        try:
            _LOGGER.debug("Fetching watch list for %s from BetaSeries", self.config_entry.title)
            watch_list, total_shows, total_episodes = await self.client.fetch_watch_list(shows_limit, episodes_limit)
        except AuthError as err:
            _log_auth_failure(self.config_entry.title, err)
            raise ConfigEntryAuthFailed from err
        except Error as err:
            _LOGGER.debug(
                "Fetching watch list for %s failed (HTTP %s): %s",
                self.config_entry.title,
                err.status,
                _compact(err.body),
            )
            raise UpdateFailed(str(err)) from err

        self.total_shows = total_shows
        self.total_episodes = total_episodes
        self.show_images = await _async_get_show_images(
            self.client, self.show_images_store, watch_list.show_ids, self.config_entry.title
        )
        return watch_list

    async def async_clean_watch_list_cache(self) -> None:
        """Force a full refetch of the watch list, artwork included, then refresh now.

        The list itself is always refetched, so only the cached show images
        need clearing: _async_get_show_images() otherwise serves them from the
        store untouched, and a show whose artwork changed would keep its stale
        one until it left and re-entered the list.

        Returns:
            None: The coordinator's data is updated in place, like any refresh.

        """
        _LOGGER.debug("Clearing cached show images for %s, forcing a full refetch", self.config_entry.title)
        await self.show_images_store.async_remove()
        await self.async_refresh()


@dataclass
class BetaSeriesData:
    """Hold the coordinators stored on the config entry's runtime_data.

    Attributes:
        member (MemberCoordinator): Coordinator for member data/stats (v1).
        planning (PlanningCoordinator): Coordinator for the upcoming episodes planning (v2).
        episodes (EpisodeCoordinator): Coordinator for the shows still to watch.

    """

    member: MemberCoordinator
    planning: PlanningCoordinator
    episodes: EpisodeCoordinator


def _upcoming_months(today: date, months_ahead: int) -> list[str]:
    """Build the list of "YYYY-MM" strings from this month through months_ahead later.

    Args:
        today (date): Reference date (the current month is always included).
        months_ahead (int): Number of additional months to include after the current one.

    Returns:
        list[str]: Months in chronological order, e.g. ["2026-08", "2026-09", "2026-10"].

    """
    months: list[str] = []
    year, month = today.year, today.month
    for _ in range(months_ahead + 1):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _past_months(today: date, months_behind: int) -> list[str]:
    """Build the list of "YYYY-MM" strings for the months before the current one.

    Args:
        today (date): Reference date (the current month is never included).
        months_behind (int): Number of months to include before the current one.

    Returns:
        list[str]: Months in chronological order, e.g. ["2026-06", "2026-07"].

    """
    months: list[str] = []
    year, month = today.year, today.month
    for _ in range(months_behind):
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        months.append(f"{year:04d}-{month:02d}")
    months.reverse()
    return months
