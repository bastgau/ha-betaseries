# `betaseries` - bundled BetaSeries API client

Self-contained client for the BetaSeries API (`https://api.betaseries.com`).

## Scope: this package is not sized by the integration

It is a standalone library that happens to be vendored here, and it evolves on its own terms -
it could be extracted to PyPI as-is (see `__init__.py`). Its surface therefore covers the API,
not the subset the Home Assistant side currently calls.

Several entry points below have no caller in `custom_components/betaseries/` today
(`fetch_timeline()`, `fetch_episodes_by_id()`, `fetch_show_episodes()`,
`fetch_episodes_to_watch()`, the `fetch_*` navigation helpers on the models, and the whole
timeline event hierarchy). **That is deliberate, and is not dead code**: measuring this package
against what the integration happens to use applies the wrong yardstick. Do not prune it on a
"nothing references this" basis; the criterion is whether it faithfully models the API.

## Entry points

Every entry point lives on `Client` and returns either a plain data object or one of the
collection types described below. Each maps to a single BetaSeries endpoint.

| Method                                                                  | Endpoint                | Returns                                    | Notes                                                                                                                                                                                                                                                                                                            |
| ----------------------------------------------------------------------- | ----------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fetch_member_data()`                                                   | `GET /members/infos`    | `MemberData`                               | Identity + viewing stats.                                                                                                                                                                                                                                                                                        |
| `fetch_planning(month)`                                                 | `GET /planning/member`  | `CollectionEpisode`                        | The member's schedule for one `"YYYY-MM"` month.                                                                                                                                                                                                                                                                 |
| `fetch_show_episodes(show_id)`                                          | `GET /shows/episodes`   | `CollectionEpisode`                        | All episodes of **one** show.                                                                                                                                                                                                                                                                                    |
| `fetch_episodes_by_id(episode_ids)`                                     | `GET /episodes/display` | `CollectionEpisode`                        | Accepts any number of ids in one request (bulk, like `fetch_shows`).                                                                                                                                                                                                                                             |
| `fetch_episodes_to_watch(*, exclude_characters=)`                       | `GET /episodes/list`    | `CollectionEpisode`                        | The member's unseen episodes, across shows.                                                                                                                                                                                                                                                                      |
| `fetch_episodes_to_watch_by_show(*, exclude_characters=)`               | `GET /episodes/list`    | `CollectionShow`                           | The member's unseen episodes, across shows grouped by show.                                                                                                                                                                                                                                                      |
| `fetch_watch_list(shows_limit, episodes_limit, *, exclude_characters=)` | `GET /episodes/list`    | `tuple[CollectionWatchListShow, int, int]` | Same endpoint, capped to `shows_limit` shows of `episodes_limit` episodes; keeps each show's `remaining` and returns the endpoint's own global counters, which the caps do not affect.                                                                                                                           |
| `fetch_shows(show_ids)`                                                 | `GET /shows/display`    | `CollectionShow`                           | Accepts any number of ids in one request; each `Show` comes back with `additional_information` populated.                                                                                                                                                                                                        |
| `fetch_timeline(member_id, *, nbpp=, since_id=, last_id=, types=)`      | `GET /timeline/member`  | `CollectionTimelineEvent`                  | The member's recent activity, paginated by event-id cursor (`since_id`/`last_id`), not by date - see [`docs/watch-history-calendar-exploration.md`](../../../docs/watch-history-calendar-exploration.md). Only `EpisodeWatchedEvent`/`SeasonWatchedEvent` are modeled; any other event type is silently dropped. |
| `search_shows(title, *, limit=)`                                        | `GET /shows/search`     | `tuple[Show, ...]`                         | Catalog search, ordered by popularity. Returns an ordered tuple, not a `CollectionShow`: the ranking is the point of a search, and `CollectionShow` is an id-keyed lookup with no iteration API. Each `Show` carries `additional_information`, `in_account` included.                                            |

`Auth` (in `auth.py`) is a separate entry point used only during initial authentication
(OAuth device flow: device code request, polling, and a minimal `fetch_member_identity()` -
see its own docstrings).

`Client(session, api_key, access_token, locale="fr")` sends `locale` as a query param on every
request above (BetaSeries' own documented default, see its OpenAPI spec's `LocaleParam`) -
it controls the language of returned text (genres, descriptions, error messages).

The three `/episodes/list` methods take `exclude_characters` (default `False`, the endpoint's own
behavior): pass `True` to send `excludes=characters` and drop the cast the client never parses.
The key still comes back, as an empty list - the payload shrinks without changing shape. The param
is a boolean rather than a list of values because `excludes`, despite accepting comma-separated
values, only honors `characters` (verified).

## Classes and how to enrich them

Two paired concepts, `Episode`/`Show`, each available standalone or as a collection:

| Class               | Wraps                 | Key attributes                                                                                                                                                             |
| ------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Episode`           | -                     | `id, season, number, code, title, description, air_date, seen, platforms, resource_url, show: Show`                                                                        |
| `Show`              | -                     | `id, title, description, slug, resource_url (property, derived from slug), additional_information: ShowAdditionalInformation \| None, episodes: CollectionEpisode \| None` |
| `CollectionEpisode` | `tuple[Episode, ...]` | `show_ids` (unique show ids referenced)                                                                                                                                    |
| `CollectionShow`    | `dict[str, Show]`     | `for_show(show_id)`                                                                                                                                                        |

A third concept, timeline events (`fetch_timeline`'s result), models only the two event types a
watch-history calendar would need - not a general-purpose activity feed:

| Class                     | Extends                     | Key attributes                                                                                                                                                                                                                             |
| ------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `TimelineEvent`           | -                           | `id, date` - common base, never instantiated directly.                                                                                                                                                                                     |
| `EpisodeWatchedEvent`     | `TimelineEvent`             | `episode_id, show: Show \| None, episode: Episode \| None` - a single episode marked watched (`TimelineEventType.EPISODE_WATCHED`, raw value `"markas"`).                                                                                  |
| `SeasonWatchedEvent`      | `TimelineEvent`             | `show_id, season, show: Show \| None` - a whole season marked watched at once (`TimelineEventType.SEASON_WATCHED`, raw value `"season_watched"`). No episode-level detail is available from this event alone - see the design notes below. |
| `CollectionTimelineEvent` | `tuple[TimelineEvent, ...]` | `fetch_shows(client)`, `fetch_episodes(client)` (see below).                                                                                                                                                                               |

`TimelineEventType` (a `StrEnum`) lists 7 raw values observed in practice (`markas`,
`season_watched`, `add_serie`, `del_serie`, `archive`, `unarchive`, `badge`) - BetaSeries doesn't
document an exhaustive enum for this field, so `Client._parse_timeline_event` silently drops any
event whose type isn't one of `EPISODE_WATCHED`/`SEASON_WATCHED` (known-but-unmodeled or entirely
unrecognized), rather than failing the whole `fetch_timeline()` call.

Every entry point above returns objects with the _enrichable_ fields left at their default
(`None`) - `Episode.show` is always populated (it comes from the same payload), but
`Show.additional_information` and `Show.episodes` are not, since fetching them is a separate
request. Call the matching `fetch_*` method to get them:

| On                        | Method                                 | Fetches via                                                                                                                              | Returns                                                                                                                                                                   |
| ------------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Episode`                 | `fetch_show(client)`                   | `client.fetch_shows([self.show.id])`                                                                                                     | A new `Episode` with `show` **entirely replaced** by the enriched one.                                                                                                    |
| `Show`                    | `fetch_episodes(client)`               | `client.fetch_show_episodes(self.id)`                                                                                                    | A new `Show` with only `episodes` populated (everything else untouched).                                                                                                  |
| `Show`                    | `fetch_additional_information(client)` | `client.fetch_shows([self.id])`                                                                                                          | The freshly-fetched `Show`, entirely replacing this one.                                                                                                                  |
| `CollectionEpisode`       | `fetch_shows(client)`                  | `client.fetch_shows(self.show_ids)` (one request for every referenced show)                                                              | A new `CollectionEpisode` with every episode's `show` **entirely replaced**.                                                                                              |
| `CollectionShow`          | `fetch_episodes(client)`               | `client.fetch_show_episodes(...)` once per show (no bulk endpoint)                                                                       | A new `CollectionShow` with every show's `episodes` populated (everything else untouched).                                                                                |
| `CollectionShow`          | `fetch_additional_information(client)` | `client.fetch_shows(...)` (one bulk request)                                                                                             | A new `CollectionShow` with every show **entirely replaced** by its freshly-fetched version.                                                                              |
| `CollectionTimelineEvent` | `fetch_shows(client)`                  | `client.fetch_episodes_by_id(...)` for `EpisodeWatchedEvent`, `client.fetch_shows(...)` for `SeasonWatchedEvent` (one bulk request each) | A new `CollectionTimelineEvent` with `show` (and, for `EpisodeWatchedEvent`, `episode` too) populated on every supported event.                                           |
| `CollectionTimelineEvent` | `fetch_episodes(client)`               | `client.fetch_episodes_by_id(...)` for `EpisodeWatchedEvent` only (one bulk request)                                                     | A new `CollectionTimelineEvent` with `episode` populated on every `EpisodeWatchedEvent`. `SeasonWatchedEvent` is left unchanged - it has no single `episode_id` to fetch. |

None of these mutate `self` (`Episode`/`Show` are frozen dataclasses). Two different merge
strategies, matching what each method actually fetches:

- `fetch_episodes()` (on `Show`/`CollectionShow`) only ever populates `episodes` - `Client.fetch_show_episodes()`
  doesn't return a `Show`, so there's nothing else it could refresh.
- `fetch_show()`/`fetch_shows()` (on `Episode`/`CollectionEpisode`) and `fetch_additional_information()`
  (on `Show`/`CollectionShow`) all go through `Client.fetch_shows()`, which returns a fully-populated
  `Show` (description, slug, additional*information - everything `/shows/display` has) - so these
  swap in the \_entire* fetched `Show` rather than merging one field at a time. There's no reason to
  keep an older/lighter value (e.g. a `description` from `/planning/member`) once the richer one from
  `/shows/display` is available.

In every case, if a show is unexpectedly absent from the client's response, the original `Show`
is kept as-is rather than overwritten with `None`.

### `CollectionTimelineEvent.fetch_shows()`/`fetch_episodes()`: avoiding redundant requests

Both `show` and `episode` can end up populated on an `EpisodeWatchedEvent` regardless of which of
the two methods is called first or how many times:

- `fetch_shows()` fetches the episode (`GET /episodes/display` returns the full episode either
  way, since that's the only way to reach its show) and stores **both** `show` and `episode` from
  that single request - not just `show` - so a later `fetch_episodes()` call has nothing left to
  fetch for that event.
- `fetch_episodes()` skips any event that already has an `episode`. If the event already has a
  `show` (from a prior `fetch_shows()`) but no `episode` yet, the freshly-fetched episode still
  carries its own `show` (the API returns it for free) - that duplicate is discarded in favor of
  the event's existing `show`, so the two never disagree.
- Either method skips any event that already has the field it would otherwise fetch, and only
  issues a request for the events actually missing it (deduplicated by id, one bulk request
  regardless of how many events share the same `episode_id`/`show_id`).

Net effect: calling `fetch_shows()` then `fetch_episodes()` (or the reverse) on the same
`CollectionTimelineEvent` never issues more than one `fetch_episodes_by_id()` call and one
`fetch_shows()` call in total, no matter the order.

`SeasonWatchedEvent.show` is populated by fetching its `show_id` directly (`client.fetch_shows()`)

- no episode is involved, so `fetch_episodes()` has nothing to do for this event type.

`ShowAdditionalInformation` (genres, showrunners, aliases, seasons, followers, network,
country, language, length, rating, notes, trailer_url, resource_url, `images: ShowImages`,
creation, broadcast_status, platforms, in_account) and `ShowImages`
(show/banner/box/poster/clearlogo URLs, all hosted on the public `pictures.betaseries.com`
CDN - no auth needed to load them) are plain data, only ever constructed by
`Client.fetch_shows()` and `Client.search_shows()`.

The last four fields are the show's _state_ rather than its description:
`creation` (year), `broadcast_status` (`"Continuing"`/`"Ended"` - named apart from `rating`,
which is a content rating), `platforms` (SVOD names, read from `platforms.svods[].name`) and
`in_account` (is this show in the authenticated member's account). All four come from the same
payload as the rest and are parsed with the same `.get(key) or <fallback>` discipline, so a
show that omits them simply reads as `None`/`()`/`False`.

## Design notes

- **The client absorbs every API quirk.** Domain classes (`Episode`, `Show`, ...) never see
  raw JSON - inconsistent nesting, `/shows/display`'s singular-vs-plural response shape
  (`{"show": {...}}` for one id vs `{"shows": [...]}` for several), stringified numbers,
  etc. are all normalized inside `Client`'s `_parse_*`/`_fetch_shows` methods.
- **Reused parsing across endpoints.** `_parse_episode()` (wrapped by `_parse_episodes()` for a
  whole payload list) is shared by `fetch_planning`, `fetch_show_episodes`, `fetch_episodes_by_id`
  and `fetch_episodes_to_watch` even though the source endpoints have different-shaped `show`
  sub-objects - fields common to all of them (`id`, `title`) are read directly, optional ones
  present on only some (`show.description`/`show.slug`, only on `/planning/member`) are read via
  `.get(...)` (returning `None` when absent) so the others don't need them. No fallback
  between fields happens here - e.g. Episode.description is never substituted with the show's
  when empty; that decision belongs to callers (see custom_components/betaseries/calendar.py).
- **`_parse_episodes()` deduplicates `Show` instances within a batch.** Episodes referencing the
  same show id (by id, not just equal value) share a single `Show` object instead of each
  rebuilding an equal-but-distinct copy - relevant when many episodes of the same show appear in
  one response (e.g. `fetch_episodes_by_id` with several episode ids from the same show, or
  `fetch_planning` for a month with many aired episodes of one series).
- **Timeline events aren't a general-purpose parser.** `_parse_timeline_event()` only recognizes
  `EPISODE_WATCHED`/`SEASON_WATCHED` and returns `None` for everything else - it isn't meant to
  eventually cover every `TimelineEventType` value, only the ones a watch-history calendar needs
  (see [`docs/watch-history-calendar-exploration.md`](../../../docs/watch-history-calendar-exploration.md)).
  `SeasonWatchedEvent`'s `show_id`/`season` are parsed from the raw `ref` field
  (`"{show_id}.{season}"`) - `ref_id` is always `0` for this event type and carries no information.
- **`Show.resource_url` is derived, not fetched.** Most URLs/fields in this client are read
  verbatim from the API's own response; this one is computed from `slug` using BetaSeries' own
  stable URL pattern (`https://www.betaseries.com/serie/{slug}`, verified via `/shows/display`) -
  because the embedded `show` sub-object of `/planning/member` carries a `slug` but never a
  ready-made `resource_url` for the show itself (only `Episode.resource_url`, a different URL,
  is given directly).
- **`ShowAdditionalInformation.trailer_url` is derived too, and deliberately incomplete.** The API
  returns a trailer as two raw fields, `next_trailer` (a bare video id) and `next_trailer_host`
  (the platform it belongs to) - `_trailer_url()` in `client.py` combines them into a playable
  URL, but only when the host is `"youtube"`, the only one confirmed in practice (see
  `bruno/Shows/display.bru`). Any other host, or no trailer at all, yields `None` rather than a
  guessed URL template for a host that was never verified.
- **Enrichment is always a separate request, never assumed.** Nothing pre-fetches
  `additional_information` or `episodes` "just in case" - callers ask for exactly what they
  need, when they need it.
