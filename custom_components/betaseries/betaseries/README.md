# `betaseries` - bundled BetaSeries API client

Self-contained client for the BetaSeries API (`https://api.betaseries.com`).

## Entry points

Every entry point lives on `Client` and returns either a plain data object or one of the
collection types described below. Each maps to a single BetaSeries endpoint.

| Method | Endpoint | Returns | Notes |
|---|---|---|---|
| `fetch_member_data()` | `GET /members/infos` | `MemberData` | Identity + viewing stats. |
| `fetch_planning(month)` | `GET /planning/member` | `CollectionEpisode` | The member's schedule for one `"YYYY-MM"` month. |
| `fetch_show_episodes(show_id)` | `GET /shows/episodes` | `CollectionEpisode` | All episodes of **one** show. |
| `fetch_episodes_to_watch()` | `GET /episodes/list` | `CollectionEpisode` | The member's unseen episodes, across shows. |
| `fetch_episodes_to_watch_by_show()` | `GET /episodes/list` | `CollectionShow` | The member's unseen episodes, across shows grouped by show. |
| `fetch_shows(show_ids)` | `GET /shows/display` | `CollectionShow` | Accepts any number of ids in one request; each `Show` comes back with `additional_information` populated. |

`Auth` (in `auth.py`) is a separate entry point used only during initial authentication
(OAuth device flow: device code request, polling, and a minimal `fetch_member_identity()` -
see its own docstrings).

`Client(session, api_key, access_token, locale="fr")` sends `locale` as a query param on every
request above (BetaSeries' own documented default, see its OpenAPI spec's `LocaleParam`) -
it controls the language of returned text (genres, descriptions, error messages).

## Classes and how to enrich them

Two paired concepts, `Episode`/`Show`, each available standalone or as a collection:

| Class | Wraps | Key attributes |
|---|---|---|
| `Episode` | - | `id, season, number, code, title, description, air_date, seen, platforms, resource_url, show: Show` |
| `Show` | - | `id, title, description, slug, resource_url (property, derived from slug), additional_information: ShowAdditionalInformation \| None, episodes: CollectionEpisode \| None` |
| `CollectionEpisode` | `tuple[Episode, ...]` | `show_ids` (unique show ids referenced) |
| `CollectionShow` | `dict[str, Show]` | `for_show(show_id)` |

Every entry point above returns objects with the *enrichable* fields left at their default
(`None`) - `Episode.show` is always populated (it comes from the same payload), but
`Show.additional_information` and `Show.episodes` are not, since fetching them is a separate
request. Call the matching `fetch_*` method to get them:

| On | Method | Fetches via | Returns |
|---|---|---|---|
| `Episode` | `fetch_show(client)` | `client.fetch_shows([self.show.id])` | A new `Episode` with `show` **entirely replaced** by the enriched one. |
| `Show` | `fetch_episodes(client)` | `client.fetch_show_episodes(self.id)` | A new `Show` with only `episodes` populated (everything else untouched). |
| `Show` | `fetch_additional_information(client)` | `client.fetch_shows([self.id])` | The freshly-fetched `Show`, entirely replacing this one. |
| `CollectionEpisode` | `fetch_shows(client)` | `client.fetch_shows(self.show_ids)` (one request for every referenced show) | A new `CollectionEpisode` with every episode's `show` **entirely replaced**. |
| `CollectionShow` | `fetch_episodes(client)` | `client.fetch_show_episodes(...)` once per show (no bulk endpoint) | A new `CollectionShow` with every show's `episodes` populated (everything else untouched). |
| `CollectionShow` | `fetch_additional_information(client)` | `client.fetch_shows(...)` (one bulk request) | A new `CollectionShow` with every show **entirely replaced** by its freshly-fetched version. |

None of these mutate `self` (`Episode`/`Show` are frozen dataclasses). Two different merge
strategies, matching what each method actually fetches:
- `fetch_episodes()` (on `Show`/`CollectionShow`) only ever populates `episodes` - `Client.fetch_show_episodes()`
  doesn't return a `Show`, so there's nothing else it could refresh.
- `fetch_show()`/`fetch_shows()` (on `Episode`/`CollectionEpisode`) and `fetch_additional_information()`
  (on `Show`/`CollectionShow`) all go through `Client.fetch_shows()`, which returns a fully-populated
  `Show` (description, slug, additional_information - everything `/shows/display` has) - so these
  swap in the *entire* fetched `Show` rather than merging one field at a time. There's no reason to
  keep an older/lighter value (e.g. a `description` from `/planning/member`) once the richer one from
  `/shows/display` is available.

In every case, if a show is unexpectedly absent from the client's response, the original `Show`
is kept as-is rather than overwritten with `None`.

`ShowAdditionalInformation` (genres, showrunners, aliases, seasons, followers, network,
country, language, length, rating, notes, next_trailer, resource_url, `images: ShowImages`)
and `ShowImages` (show/banner/box/poster/clearlogo URLs, all hosted on the public
`pictures.betaseries.com` CDN - no auth needed to load them) are plain data, only ever
constructed by `Client.fetch_shows()`.

## Design notes

- **The client absorbs every API quirk.** Domain classes (`Episode`, `Show`, ...) never see
  raw JSON - inconsistent nesting, `/shows/display`'s singular-vs-plural response shape
  (`{"show": {...}}` for one id vs `{"shows": [...]}` for several), stringified numbers,
  etc. are all normalized inside `Client`'s `_parse_*`/`_fetch_shows` methods.
- **Reused parsing across endpoints.** `_parse_episode()` is shared by `fetch_planning`,
  `fetch_show_episodes` and `fetch_episodes_to_watch` even though the three source endpoints
  have different-shaped `show` sub-objects - fields common to all three (`id`, `title`) are
  read directly, optional ones present on only some (`show.description`/`show.slug`, only on
  `/planning/member`) are read via `.get(...)` (returning `None` when absent) so the others
  don't need them. No fallback
  between fields happens here - e.g. Episode.description is never substituted with the show's
  when empty; that decision belongs to callers (see custom_components/betaseries/calendar.py).
- **`Show.resource_url` is derived, not fetched.** Unlike every other URL/field in this client
  (always read verbatim from the API's own response), it's computed from `slug` using
  BetaSeries' own stable URL pattern (`https://www.betaseries.com/serie/{slug}`, verified via
  `/shows/display`) - because the embedded `show` sub-object of `/planning/member` carries a
  `slug` but never a ready-made `resource_url` for the show itself (only `Episode.resource_url`,
  a different URL, is given directly).
- **Enrichment is always a separate request, never assumed.** Nothing pre-fetches
  `additional_information` or `episodes` "just in case" - callers ask for exactly what they
  need, when they need it.
