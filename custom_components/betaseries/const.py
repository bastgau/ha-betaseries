"""Constants for the Home Assistant BetaSeries integration.

Constants specific to the BetaSeries API itself (URLs, endpoints, error
codes) live in the self-contained betaseries/const.py sub-package instead.
"""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "betaseries"

DEFAULT_MEMBER_SCAN_INTERVAL = timedelta(minutes=15)
