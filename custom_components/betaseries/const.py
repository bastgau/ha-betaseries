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

# Number of months fetched per planning refresh (current + this many ahead),
# giving calendar.py enough lookahead to answer async_get_events() requests
# that span slightly beyond the current month without an extra API round trip.
PLANNING_MONTHS_AHEAD = 2
