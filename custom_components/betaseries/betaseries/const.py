"""Constants for the BetaSeries API itself."""

from __future__ import annotations

BASE_URL = "https://api.betaseries.com"
OAUTH_DEVICE_ENDPOINT = "/oauth/device"
OAUTH_TOKEN_ENDPOINT = "/oauth/access_token"  # noqa: S105 (endpoint path, not a secret)
MEMBERS_INFOS_ENDPOINT = "/members/infos"
PLANNING_MEMBER_ENDPOINT = "/planning/member"
EPISODES_LIST_ENDPOINT = "/episodes/list"
SHOWS_DISPLAY_ENDPOINT = "/shows/display"
SHOWS_EPISODES_ENDPOINT = "/shows/episodes"

# Required on every request (see api.betaseries.com docs).
API_VERSION = "3.0"

# BetaSeries returns this numeric code (not the localized text) while the
# device code has not been validated yet on their website.
ERROR_CODE_PENDING = 2001

# BetaSeries also returns code 2001 (same number, unrelated meaning) on
# authenticated data endpoints (e.g. /members/infos) when the access token
# itself is no longer accepted (HTTP 400, not 401).
ERROR_CODE_INVALID_CREDENTIALS = 2001

# BetaSeries returns this code (HTTP 400, not 401) when the X-BetaSeries-Key
# (api_key/client_id) itself is invalid/unknown - "Mauvaise clé API." -
# verified from a real rejected api_key in production.
ERROR_CODE_INVALID_API_KEY = 1001

# Codes observed on authenticated data endpoints that mean "the stored
# credentials are no longer accepted" - both must trigger reauthentication.
INVALID_CREDENTIALS_ERROR_CODES = frozenset({ERROR_CODE_INVALID_API_KEY, ERROR_CODE_INVALID_CREDENTIALS})
