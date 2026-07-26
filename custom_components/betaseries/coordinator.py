"""Data update coordinator for the BetaSeries integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .betaseries import AuthError, Error, PlanningEpisode
from .const import (
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES,
    DEFAULT_PLANNING_MONTHS_AHEAD,
    DEFAULT_PLANNING_MONTHS_BEHIND,
    DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    PLANNING_STORE_KEY_PREFIX,
    PLANNING_STORE_VERSION,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .betaseries import Client, MemberData

_LOGGER = logging.getLogger(__name__)

type BetaSeriesConfigEntry = ConfigEntry["BetaSeriesData"]


class MemberCoordinator(DataUpdateCoordinator["MemberData"]):
    """Fetch member data and statistics (GET /members/infos, see CLAUDE.md §5).

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch member data.

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

    async def _async_update_data(self) -> MemberData:
        """Fetch the latest member data.

        Returns:
            MemberData: The member's id, login, xp and viewing statistics.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        try:
            _LOGGER.debug("Fetching member data for %s from BetaSeries", self.config_entry.title)
            return await self.client.fetch_member_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(str(err)) from err


class PlanningCoordinator(DataUpdateCoordinator[tuple["PlanningEpisode", ...]]):
    """Fetch the member's planning (GET /planning/member, see CLAUDE.md §4).

    Past months are fetched once and cached in a Store (they never change
    once the month is over), so regular refreshes only re-fetch the current
    and future months. If the configured months_behind grows, the missing
    older months are fetched and added to the cache.

    Attributes:
        config_entry (BetaSeriesConfigEntry): The config entry this coordinator serves.
        client (Client): The BetaSeries API client used to fetch the planning.
        store (Store[dict[str, list[dict[str, Any]]]]): Persisted cache of past months' episodes.

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
        self.store: Store[dict[str, list[dict[str, Any]]]] = Store(
            hass, PLANNING_STORE_VERSION, f"{PLANNING_STORE_KEY_PREFIX}_{config_entry.entry_id}"
        )

    async def _async_update_data(self) -> tuple[PlanningEpisode, ...]:
        """Fetch the current/future planning and merge it with the cached past months.

        Returns:
            tuple[PlanningEpisode, ...]: The member's episodes, sorted by air_date.

        Raises:
            ConfigEntryAuthFailed: If the stored access token was rejected.
            UpdateFailed: If the request fails for any other reason.

        """
        # NumberSelector-backed options always come back as float (see config_flow.py),
        # but range()/list indexing below require int.
        months_ahead = int(self.config_entry.options.get(CONF_PLANNING_MONTHS_AHEAD, DEFAULT_PLANNING_MONTHS_AHEAD))
        months_behind = int(
            self.config_entry.options.get(CONF_PLANNING_MONTHS_BEHIND, DEFAULT_PLANNING_MONTHS_BEHIND)
        )
        today = dt_util.now().date()

        try:
            past_by_month = await self._async_get_cached_past_months(_past_months(today, months_behind))
            current_and_future = [
                await self._async_fetch_planning(month) for month in _upcoming_months(today, months_ahead)
            ]
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(str(err)) from err

        episodes = (episode for episodes in (*past_by_month.values(), *current_and_future) for episode in episodes)
        return tuple(sorted(episodes, key=lambda episode: episode.air_date))

    async def _async_fetch_planning(self, month: str) -> tuple[PlanningEpisode, ...]:
        """Fetch a single month's planning, logging the account name beforehand.

        Errors from the underlying request propagate to the caller unchanged.

        Args:
            month (str): Month to fetch, as "YYYY-MM".

        Returns:
            tuple[PlanningEpisode, ...]: The member's episodes for that month.

        """
        _LOGGER.debug("Fetching planning for %s (month=%s) from BetaSeries", self.config_entry.title, month)
        return await self.client.fetch_planning(month)

    async def _async_get_cached_past_months(self, months: list[str]) -> dict[str, tuple[PlanningEpisode, ...]]:
        """Return past months' episodes, fetching and caching any that are missing.

        Errors from fetching a missing month propagate to the caller unchanged.

        Args:
            months (list[str]): Past "YYYY-MM" months that should be in the cache.

        Returns:
            dict[str, tuple[PlanningEpisode, ...]]: Episodes for each requested month.

        """
        stored = await self.store.async_load() or {}
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
            await self.store.async_save(stored)

        return {month: tuple(_episode_from_dict(data) for data in stored[month]) for month in months}


def _episode_to_dict(episode: PlanningEpisode) -> dict[str, Any]:
    """Serialize a PlanningEpisode for storage (date -> ISO string).

    Args:
        episode (PlanningEpisode): The episode to serialize.

    Returns:
        dict[str, Any]: A JSON-serializable representation of the episode.

    """
    data = asdict(episode)
    data["air_date"] = episode.air_date.isoformat()
    return data


def _episode_from_dict(data: dict[str, Any]) -> PlanningEpisode:
    """Deserialize a PlanningEpisode from storage (ISO string -> date).

    Args:
        data (dict[str, Any]): The stored representation of the episode.

    Returns:
        PlanningEpisode: The deserialized episode.

    """
    return PlanningEpisode(
        id=data["id"],
        show_id=data["show_id"],
        show_title=data["show_title"],
        season=data["season"],
        episode=data["episode"],
        code=data["code"],
        title=data["title"],
        description=data["description"],
        air_date=date.fromisoformat(data["air_date"]),
        seen=data["seen"],
        platforms=tuple(data["platforms"]),
        resource_url=data["resource_url"],
    )


@dataclass
class BetaSeriesData:
    """Hold the coordinators stored on the config entry's runtime_data.

    Attributes:
        member (MemberCoordinator): Coordinator for member data/stats (v1).
        planning (PlanningCoordinator): Coordinator for the upcoming episodes planning (v2).

    """

    member: MemberCoordinator
    planning: PlanningCoordinator


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
