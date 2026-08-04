"""Constants for the BetaSeries API itself."""

from __future__ import annotations

BASE_URL = "https://api.betaseries.com"
OAUTH_DEVICE_ENDPOINT = "/oauth/device"
OAUTH_TOKEN_ENDPOINT = "/oauth/access_token"  # noqa: S105 (endpoint path, not a secret)
MEMBERS_INFOS_ENDPOINT = "/members/infos"
PLANNING_MEMBER_ENDPOINT = "/planning/member"
EPISODES_LIST_ENDPOINT = "/episodes/list"
EPISODES_DISPLAY_ENDPOINT = "/episodes/display"
SHOWS_DISPLAY_ENDPOINT = "/shows/display"
SHOWS_EPISODES_ENDPOINT = "/shows/episodes"
TIMELINE_MEMBER_ENDPOINT = "/timeline/member"
MEMBERS_BADGES_ENDPOINT = "/members/badges"
EPISODES_WATCHED_ENDPOINT = "/episodes/watched"
EPISODES_NOTE_ENDPOINT = "/episodes/note"
SEASONS_WATCHED_ENDPOINT = "/seasons/watched"
SEASONS_NOTE_ENDPOINT = "/seasons/note"
SHOWS_NOTE_ENDPOINT = "/shows/note"

# GET /episodes/list embeds the full cast of every returned episode under
# "characters". Value of the `excludes` query param that drops it, sent only
# when the caller asks for it (see Client.fetch_watch_list). Verified via Bruno
# (bruno/Episodes/list.bru): the key then comes back as an empty list, so the
# payload shrinks without changing its shape.
#
# `excludes` takes a comma-separated list, but "characters" is the only value
# that actually removes anything (verified) - hence a single constant and a
# boolean flag on the client, rather than a caller-supplied list of values that
# would suggest a flexibility the endpoint does not have. It is also specific to
# this endpoint: the other ones this client reads ignore it, /planning/member
# included, so its heavy payload cannot be trimmed this way.
EPISODES_LIST_EXCLUDE_CHARACTERS = "characters"

# Deadline for a single request, in seconds. Declared rather than inherited:
# aiohttp defaults to a 300 s total, which would let one call stall a
# coordinator refresh for five minutes, and could change without us deciding.
# Measured against a real account, a request takes 0.1-0.5 s (the heaviest
# being one month of planning), so this leaves roughly sixty times the
# observed worst case for slow links.
REQUEST_TIMEOUT_SECONDS = 30

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

# BetaSeries returns this code (HTTP 400) on /episodes/note, /seasons/note and
# DELETE /episodes/watched when the target episode/season is not marked as
# watched - verified via Bruno on all three (bruno/Episodes/note.bru,
# bruno/Seasons/note.bru, bruno/Episodes/unwatched.bru). Same number reused
# across granularities, error text always mentions "episode" even in a season
# context.
ERROR_CODE_NOT_WATCHED = 2005
