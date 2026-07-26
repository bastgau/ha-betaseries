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

# Storage key for the cached past-months planning (see PlanningCoordinator).
PLANNING_STORE_VERSION = 1
PLANNING_STORE_KEY_PREFIX = "betaseries_planning_past"
