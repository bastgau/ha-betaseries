"""Constants for the Home Assistant BetaSeries integration.

Constants specific to the BetaSeries API itself (URLs, endpoints, error
codes) live in the self-contained betaseries/const.py sub-package instead.
"""

from __future__ import annotations

DOMAIN = "betaseries"

# Option keys (see CLAUDE.md §6, arbitrage #4): both scan intervals are
# user-configurable via OptionsFlow, in minutes.
CONF_MEMBER_SCAN_INTERVAL = "member_scan_interval"
CONF_PLANNING_SCAN_INTERVAL = "planning_scan_interval"
CONF_EPISODES_SCAN_INTERVAL = "episodes_scan_interval"

DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES = 15
DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES = 60
DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES = 30

MIN_MEMBER_SCAN_INTERVAL_MINUTES = 5
MAX_MEMBER_SCAN_INTERVAL_MINUTES = 120

MIN_PLANNING_SCAN_INTERVAL_MINUTES = 15
MAX_PLANNING_SCAN_INTERVAL_MINUTES = 360

MIN_EPISODES_SCAN_INTERVAL_MINUTES = 5
MAX_EPISODES_SCAN_INTERVAL_MINUTES = 120

# How much of the "still to watch" list is exposed as the shows_to_watch
# sensor's `shows` attribute (see WatchListCoordinator). Both are sent to
# GET /episodes/list as showsLimit/limit, so the payload stays small: the
# endpoint's own counters (total/totalEpisodes) are unaffected by them.
CONF_SHOWS_LIMIT = "shows_limit"
CONF_EPISODES_LIMIT = "episodes_limit"

DEFAULT_SHOWS_LIMIT = 10
DEFAULT_EPISODES_LIMIT = 2

MIN_SHOWS_LIMIT = 1
MAX_SHOWS_LIMIT = 50

MIN_EPISODES_LIMIT = 1
MAX_EPISODES_LIMIT = 10

# Number of months fetched per planning refresh, both directions around the
# current month (see CLAUDE.md §4/§6). Configurable via OptionsFlow like the
# scan intervals above. Past months are fetched once and cached (see
# coordinator.py) since they never change once the month is over.
CONF_PLANNING_MONTHS_AHEAD = "planning_months_ahead"
CONF_PLANNING_MONTHS_BEHIND = "planning_months_behind"

DEFAULT_PLANNING_MONTHS_AHEAD = 2
DEFAULT_PLANNING_MONTHS_BEHIND = 2

MIN_PLANNING_MONTHS_AHEAD = 0
MAX_PLANNING_MONTHS_AHEAD = 12

MIN_PLANNING_MONTHS_BEHIND = 0
MAX_PLANNING_MONTHS_BEHIND = 12

# Preferred language for BetaSeries' responses (genres, descriptions, error
# text, ...), sent as the "locale" query param on every Client request (see
# betaseries/const.py's LocaleParam, verified via the official OpenAPI spec -
# CLAUDE.md §8). Only "fr"/"en" are offered: the only two languages
# BetaSeries' own content is reliably localized in. Collected once when
# adding the account, then editable via OptionsFlow like the other options.
CONF_LOCALE = "locale"
DEFAULT_LOCALE = "fr"
SUPPORTED_LOCALES = ["fr", "en"]

# Storage key for the cached past-months planning (see PlanningCoordinator).
# Bump this whenever the cached Episode dict shape changes (see
# coordinator._episode_to_dict/_episode_from_dict) - _CacheStore discards
# any data from an older version instead of trying to migrate it, since this
# cache is just a performance optimization that's always safe/cheap to refill
# from the API.
PLANNING_STORE_VERSION = 1
PLANNING_STORE_KEY_PREFIX = "betaseries_planning_past"

# Storage key for the cached show images (see PlanningCoordinator). These are
# public URLs on pictures.betaseries.com (verified loadable with no auth, unlike
# the episode thumbnails - see CLAUDE.md §4), fetched in a single bulk
# GET /shows/display call for every show currently in the planning window. A
# show's images essentially never change, so only shows missing from this cache
# are fetched on each refresh, and shows that left the window are purged.
PLANNING_SHOW_IMAGES_STORE_VERSION = 1
PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX = "betaseries_planning_show_images"

# Same cache, for the shows listed by WatchListCoordinator. Kept separate from
# the planning's rather than shared: the two coordinators cover different sets
# of shows (the planning is bounded by its month window, the watch list is
# not), so a shared store would need its purge driven by the union of both -
# all that for a single extra /shows/display call on the first refresh.
EPISODE_SHOW_IMAGES_STORE_VERSION = 1
EPISODE_SHOW_IMAGES_STORE_KEY_PREFIX = "betaseries_episode_show_images"

# Storage key for the cached badge details (see MemberCoordinator). Badges are
# only refetched when stats.badges (the count from GET /members/infos) changes
# from the last known value - this persists both the count and the matching
# badge list so a HA restart doesn't force a refetch even when nothing changed.
BADGES_STORE_VERSION = 1
BADGES_STORE_KEY_PREFIX = "betaseries_badges"

# Every cache Store the coordinators create per config entry, as
# (version, key prefix) pairs. async_remove_entry (see __init__.py) walks this
# list to delete them when the entry is removed: Home Assistant never cleans
# .storage files up on its own, so a cache added above and left out here would
# outlive every entry that ever created it.
CACHE_STORES: tuple[tuple[int, str], ...] = (
    (PLANNING_STORE_VERSION, PLANNING_STORE_KEY_PREFIX),
    (PLANNING_SHOW_IMAGES_STORE_VERSION, PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX),
    (EPISODE_SHOW_IMAGES_STORE_VERSION, EPISODE_SHOW_IMAGES_STORE_KEY_PREFIX),
    (BADGES_STORE_VERSION, BADGES_STORE_KEY_PREFIX),
)
