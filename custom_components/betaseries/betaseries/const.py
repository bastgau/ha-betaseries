"""Constants for the BetaSeries API itself (independent from Home Assistant)."""

from __future__ import annotations

BASE_URL = "https://api.betaseries.com"
OAUTH_DEVICE_ENDPOINT = "/oauth/device"
OAUTH_TOKEN_ENDPOINT = "/oauth/access_token"  # noqa: S105 (endpoint path, not a secret)
MEMBERS_INFOS_ENDPOINT = "/members/infos"
PLANNING_MEMBER_ENDPOINT = "/planning/member"

# Required on every request (see api.betaseries.com docs).
API_VERSION = "3.0"

# BetaSeries returns this numeric code (not the localized text) while the
# device code has not been validated yet on their website.
ERROR_CODE_PENDING = 2001
