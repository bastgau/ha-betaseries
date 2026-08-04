"""Diagnostics platform for the BetaSeries integration.

Deliberately aggregates only: counts, totals and per-month breakdowns, never
a show or episode the member follows. These files are downloaded by users and
pasted into public issues, so what they contain is published - and a viewing
history is more personal than a set of counters. Everything here was chosen
because it would have shortened a real investigation: the option values, the
per-month spread of the planning, and each coordinator's last outcome.
"""

from __future__ import annotations

from collections import Counter
import dataclasses
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import (
    async_redact_data,  # pyright: ignore[reportUnknownVariableType]
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_CLIENT_SECRET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from .coordinator import (
        BetaSeriesConfigEntry,
        MemberCoordinator,
        PlanningCoordinator,
        WatchListCoordinator,
    )

# Credentials held in entry.data. The api_key alone identifies the BetaSeries
# application, and the access token grants full account access, so none of the
# three may reach a public issue.
TO_REDACT = {CONF_API_KEY, CONF_CLIENT_SECRET, CONF_ACCESS_TOKEN}


def _coordinator_state(coordinator: DataUpdateCoordinator[Any]) -> dict[str, Any]:
    """Summarize how a coordinator's last refresh went.

    Reports the exception's type and message but never the response body it
    may carry (see the client's Error), which is raw API output.

    Args:
        coordinator (DataUpdateCoordinator[Any]): The coordinator to describe.

    Returns:
        dict[str, Any]: Its refresh interval, last outcome and last error, if any.

    """
    interval = coordinator.update_interval
    error = coordinator.last_exception
    return {
        "last_update_success": coordinator.last_update_success,
        "update_interval_minutes": interval.total_seconds() / 60 if interval else None,
        "last_error": f"{type(error).__name__}: {error}" if error else None,
    }


def _member_diagnostics(coordinator: MemberCoordinator) -> dict[str, Any]:
    """Describe the member coordinator and the statistics it holds.

    The statistics are aggregate counters, so they are reported in full: they
    say nothing about what the member watches, and reading them side by side
    is what makes a wrong counter obvious.

    Args:
        coordinator (MemberCoordinator): The coordinator to describe.

    Returns:
        dict[str, Any]: Its refresh state, the raw statistics and the badge count.

    """
    state = _coordinator_state(coordinator)
    if not coordinator.last_update_success:
        return state
    return {
        **state,
        "stats": dataclasses.asdict(coordinator.data.stats),
        "badges": len(coordinator.data.badges),
    }


async def _planning_diagnostics(coordinator: PlanningCoordinator) -> dict[str, Any]:
    """Describe the planning coordinator, its window and its cache.

    The per-month spread and the cached months are the two things that explain
    most planning surprises: how far the window reaches, and which months are
    served from disk rather than refetched.

    Args:
        coordinator (PlanningCoordinator): The coordinator to describe.

    Returns:
        dict[str, Any]: Its refresh state, episode counts per month and cache contents.

    """
    state = _coordinator_state(coordinator)
    cached = await coordinator.planning_store.async_load() or {}
    cache = {"cached_months": {month: len(episodes) for month, episodes in sorted(cached.items())}}
    if not coordinator.last_update_success:
        return {**state, **cache}

    images = coordinator.data.images
    episodes = tuple(coordinator.data.episodes)
    return {
        **state,
        "episodes": len(episodes),
        # Episodes restored from the cache carry no watch status at all (see
        # _episode_to_dict), so the two counters are reported side by side:
        # "seen" alone would silently read as "the rest are unwatched", and
        # the unknown count doubles as how much of the window came off disk.
        "episodes_seen": sum(1 for episode in episodes if episode.seen is True),
        "episodes_seen_unknown": sum(1 for episode in episodes if episode.seen is None),
        "episodes_per_month": dict(sorted(Counter(e.air_date.strftime("%Y-%m") for e in episodes).items())),
        "shows": len(coordinator.data.episodes.show_ids),
        "shows_with_images": sum(1 for artwork in images.values() if artwork),
        "shows_without_images": sum(1 for artwork in images.values() if not artwork),
        **cache,
    }


def _watch_list_diagnostics(coordinator: WatchListCoordinator) -> dict[str, Any]:
    """Describe the coordinator behind the "shows to catch up on" sensor.

    Both totals are reported: they are the endpoint's own and ignore the
    configured limits, so comparing them with the number of shows actually
    listed tells whether a limit is truncating the list.

    Args:
        coordinator (WatchListCoordinator): The coordinator to describe.

    Returns:
        dict[str, Any]: Its refresh state, the endpoint's totals and how much of the list is held.

    """
    state = _coordinator_state(coordinator)
    if not coordinator.last_update_success:
        return state
    return {
        **state,
        "total_shows": coordinator.data.total_shows,
        "total_episodes": coordinator.data.total_episodes,
        "shows_listed": len(coordinator.data.shows),
        "shows_with_images": sum(1 for artwork in coordinator.data.images.values() if artwork),
    }


async def async_get_config_entry_diagnostics(  # pylint: disable=unused-argument
    hass: HomeAssistant,  # noqa: ARG001
    entry: BetaSeriesConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (BetaSeriesConfigEntry): The config entry to describe.

    Returns:
        dict[str, Any]: The entry's options, its redacted credentials and one block per coordinator.

    """
    data = entry.runtime_data
    return {
        "entry": {
            # The unique id is the BetaSeries member id and the title is the
            # login, so both identify the account as surely as a credential.
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "member": _member_diagnostics(data.member),
        "planning": await _planning_diagnostics(data.planning),
        "watch_list": _watch_list_diagnostics(data.watch_list),
    }
