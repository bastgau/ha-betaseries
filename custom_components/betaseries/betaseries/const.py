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

# Fields requested from GET /members/infos to feed the v1 sensors/binary_sensors
# (see CLAUDE.md §5). Keeps the payload light instead of fetching everything.
MEMBER_DATA_FIELDS = (
    "id,login,xp,"
    "stats.episodes_to_watch,stats.time_to_spend,stats.progress,"
    "stats.shows_to_watch,stats.movies_to_watch,stats.shows_current,"
    "stats.badges,stats.shows,stats.shows_finished,stats.episodes,"
    "stats.time_on_tv,stats.movies,stats.streak_days,stats.member_since_days,"
    "stats.episodes_per_month,stats.favorite_genre"
)

# GET /planning/member does not support "fields" (verified: it returns the
# full heavy payload - characters, crew, description, ... - regardless).
# It does support "unseen" and "month" (YYYY-MM), both verified to filter
# strictly server-side and to combine as an intersection.
PLANNING_UNSEEN_ONLY = "true"
