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

DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES = 15
DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES = 60

MIN_MEMBER_SCAN_INTERVAL_MINUTES = 5
MAX_MEMBER_SCAN_INTERVAL_MINUTES = 120

MIN_PLANNING_SCAN_INTERVAL_MINUTES = 15
MAX_PLANNING_SCAN_INTERVAL_MINUTES = 360

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
# coordinator._episode_to_dict/_episode_from_dict) - _PastMonthsStore discards
# any data from an older version instead of trying to migrate it, since this
# cache is just a performance optimization that's always safe/cheap to refill
# from the API. Bumped 1 -> 2: Episode's "number" field used to be persisted
# as "episode", crashing _episode_from_dict (KeyError: 'number') on any cache
# left over from before that rename. Bumped 2 -> 3: added "show_description"/
# "show_slug" keys (Show.description/Show.slug) - additive, but past months
# never get refetched once cached, so without this bump a pre-existing cache
# would silently keep missing these fields forever instead of just once.
PLANNING_STORE_VERSION = 3
PLANNING_STORE_KEY_PREFIX = "betaseries_planning_past"
