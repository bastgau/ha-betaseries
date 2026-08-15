"""Constants for the Home Assistant BetaSeries integration.

Constants specific to the BetaSeries API itself (URLs, endpoints, error
codes) live in the self-contained betaseries/const.py sub-package instead.
"""

from __future__ import annotations

DOMAIN = "betaseries"
API_URL = "https://www.betaseries.com/api/"

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

# How much of the "still to watch" list is exposed as the shows_to_catch_up_on
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

# Whether the watch list sensor also exposes a `data` attribute shaped for
# third-party media cards (e.g. custom-cards/upcoming-media-card). Off by
# default: building it costs one extra pass over the listed shows and ~8 kB
# on the entity's state, for users who never installed such a card.
CONF_UPCOMING_MEDIA_CARD = "upcoming_media_card"
DEFAULT_UPCOMING_MEDIA_CARD = False

# Number of months fetched per planning refresh, both directions around the
# current month (see CLAUDE.md §4/§6). Configurable via OptionsFlow like the
# scan intervals above. Past months are fetched once and cached (see
# coordinator.py) since they never change once the month is over.
CONF_PLANNING_MONTHS_AHEAD = "planning_months_ahead"
CONF_PLANNING_MONTHS_BEHIND = "planning_months_behind"

DEFAULT_PLANNING_MONTHS_AHEAD = 2
DEFAULT_PLANNING_MONTHS_BEHIND = 2

# Same ceiling both ways, but the two directions do not cost the same thing,
# which is what makes this ceiling matter on one side only. A past month is
# fetched once and then served from the Store forever, so months_behind costs
# that many requests on the first refresh and ~1 per month elapsed afterwards.
# Future months are refetched on *every* refresh (their schedule still moves),
# so months_ahead costs months_ahead + 1 requests each time - and BetaSeries
# has barely any announced schedule to return more than a few months out.
# Raising months_behind is nearly free; raising months_ahead is not.
MIN_PLANNING_MONTHS_AHEAD = 0
MAX_PLANNING_MONTHS_AHEAD = 2

MIN_PLANNING_MONTHS_BEHIND = 0
MAX_PLANNING_MONTHS_BEHIND = 24

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
# list to delete them when the entry is removed: Home Assistant never clears
# .storage files up on its own, so a cache added above and left out here would
# outlive every entry that ever created it.
CACHE_STORES: tuple[tuple[int, str], ...] = (
    (PLANNING_STORE_VERSION, PLANNING_STORE_KEY_PREFIX),
    (PLANNING_SHOW_IMAGES_STORE_VERSION, PLANNING_SHOW_IMAGES_STORE_KEY_PREFIX),
    (EPISODE_SHOW_IMAGES_STORE_VERSION, EPISODE_SHOW_IMAGES_STORE_KEY_PREFIX),
    (BADGES_STORE_VERSION, BADGES_STORE_KEY_PREFIX),
)

# v3 services (see CLAUDE.md §8): names match services.yaml/strings.json exactly.
SERVICE_MARK_EPISODE_WATCHED = "mark_episode_watched"
SERVICE_MARK_EPISODE_UNWATCHED = "mark_episode_unwatched"
SERVICE_RATE_EPISODE = "rate_episode"
SERVICE_UNRATE_EPISODE = "unrate_episode"
SERVICE_MARK_SEASON_WATCHED = "mark_season_watched"
SERVICE_MARK_SEASON_UNWATCHED = "mark_season_unwatched"
SERVICE_RATE_SEASON = "rate_season"
SERVICE_UNRATE_SEASON = "unrate_season"
SERVICE_RATE_SHOW = "rate_show"
SERVICE_UNRATE_SHOW = "unrate_show"
SERVICE_DELETE_TOKEN = "delete_token"  # noqa: S105
# Catalog search and its natural follow-up. search_shows is the only service
# that returns data (SupportsResponse.ONLY): it answers a question instead of
# changing something, which is also why it is the only one usable from a
# dashboard card without side effects.
SERVICE_SEARCH_SHOWS = "search_shows"
SERVICE_ADD_SHOW = "add_show"
SERVICE_REMOVE_SHOW = "remove_show"

# Service field names. ATTR_CONFIG_ENTRY targets the BetaSeries account
# (ConfigEntrySelector, see services.py); episode_id/show_id mirror the
# attribute names sensors already expose (CLAUDE.md §5), so a value copied
# from a dashboard card matches the service field verbatim.
ATTR_CONFIG_ENTRY = "config_entry"
ATTR_EPISODE_ID = "episode_id"
ATTR_SHOW_ID = "show_id"
ATTR_SEASON = "season"
ATTR_NOTE = "note"
ATTR_QUERY = "query"
ATTR_LIMIT = "limit"

# Bounds of search_shows' `limit` field. The API accepts up to 100 per page;
# 50 is enough for any dashboard use and keeps a single response small enough
# to travel over the websocket without thought.
SEARCH_SHOWS_MIN_LIMIT = 1
SEARCH_SHOWS_MAX_LIMIT = 50
SEARCH_SHOWS_DEFAULT_LIMIT = 20
