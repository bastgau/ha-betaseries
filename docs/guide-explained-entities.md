## Entities & Services

This integration connects Home Assistant to your [BetaSeries](https://www.betaseries.com/) account: viewing statistics and watchlist metrics as sensors, upcoming episodes on a calendar, and actions to mark episodes as watched or rate them directly from Home Assistant.

A few entities are disabled by default (diagnostic sensor, cache-purge buttons). You have to enable them to display / use them.

The entity id follows the entity's `translation_key`, under the `betaseries` domain (_sensor.betaseries\_\<translation_key\>_).

### Sensors

Your BetaSeries account statistics (episodes/movies watched, progress, badges...) and watchlist metrics (what's next to watch, release dates), refreshed on a schedule from the integration options.

<details>
  <summary>Display the sensors</summary>

| Name                    | Unit           | Meaning                                                                                                              | Enabled |
| ----------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------- | ------- |
| Episodes to watch       | episodes       | Number of episodes available to watch                                                                                | yes     |
| Time to spend           | minutes        | Minutes left to watch everything pending                                                                             | yes     |
| Progress                | %              | Overall watch progress                                                                                               | yes     |
| Shows not started       | shows          | Number of shows never started, archived ones included                                                                | yes     |
| Movies to watch         | movies         | Number of movies not yet watched                                                                                     | yes     |
| Shows in progress       | shows          | Number of shows started and not yet finished                                                                         | yes     |
| Badges                  | badges         | Number of badges earned                                                                                              | yes     |
| Shows total             | shows          | Total number of shows followed, archived ones included                                                               | yes     |
| Shows finished          | shows          | Number of shows BetaSeries counts as finished, archived ones included                                                | yes     |
| Episodes watched        | episodes       | Total number of episodes watched                                                                                     | yes     |
| Time on TV              | minutes        | Total minutes spent watching episodes                                                                                | yes     |
| Movies total            | movies         | Total number of movies watched                                                                                       | yes     |
| XP                      | xp             | Member experience points                                                                                             | yes     |
| Streak days             | days           | Current daily streak                                                                                                 | yes     |
| Membership duration     | days           | Number of days since account creation                                                                                | yes     |
| Episodes per month      | episodes/month | Average number of episodes watched per month                                                                         | yes     |
| Favorite genre          | -              | Most watched genre                                                                                                   | yes     |
| Previous episode airing | -              | Air date of the most recently aired episode, watched or not (excluding today)                                        | yes     |
| Next episode airing     | -              | Air date of the next episode due to air, watched or not (including today)                                            | yes     |
| Shows to catch up on    | shows          | Number of shows with pending episodes; detailed show/episode information is in the entity attributes                 | yes     |
| Suggestion of the day   | -              | One episode to watch today, picked once a day from the shows you have to catch up on                                 | yes     |
| Calendar event count    | -              | Diagnostic sensor: total number of episodes currently loaded by the calendar, broken down by month in its attributes | no      |

#### - Previous / Next episode airing

**Name:** sensor.betaseries_previous_episode_airing / sensor.betaseries_next_episode_airing
**Description:** Release dates, never about what you have watched - an episode airing today always belongs to "next".
**Attributes:** The episode each sensor points at.

```json
{
  "episode_id": "3905073",
  "show_id": "38605",
  "code": "S06E01",
  "season": 6,
  "number": 1,
  "title": "Joan Is Awful",
  "show_title": "Black Mirror",
  "platforms": ["Netflix"],
  "resource_url": "https://www.betaseries.com/...",
  "show_images": { "poster": "https://pictures.betaseries.com/..." }
}
```

> The poster (`show_images`) is also set as the entity picture, so both sensors render as-is in a `picture-entity` card. How far back "previous" can see is bounded by the calendar's own window (2 months by default).

With the `upcoming_media_card` integration option turned on (see
[Lovelace cards](../README.md#lovelace-cards) in the README), each sensor also carries a `data`
attribute: the single episode it points at, shaped for the third-party
[upcoming-media-card](https://github.com/custom-cards/upcoming-media-card). No `flag`: this is
about an air date, not a watch status.

```json
{
  "data": [
    {
      "title_default": "$title",
      "line1_default": "$episode",
      "line2_default": "$number",
      "line3_default": "$date",
      "line4_default": "$empty",
      "icon": "mdi:calendar-star"
    },
    {
      "airdate": "2026-05-29",
      "title": "Black Mirror",
      "episode": "Joan Is Awful",
      "number": "S06E01",
      "poster": "https://pictures.betaseries.com/...",
      "fanart": null,
      "deep_link": "https://www.betaseries.com/episode/3905073",
      "summary": "A tech CEO watches her life turned into a streaming show overnight.",
      "rating": 3.89,
      "studio": "Netflix",
      "genres": ["Science Fiction", "Drama"],
      "trailer": "https://www.youtube.com/watch?v=ZDdijwdg7s8"
    }
  ]
}
```

#### - Shows to catch up on

**Name:** sensor.betaseries_shows_to_catch_up_on
**Description:** Number of shows with at least one unseen episode.
**Unit:** shows
**Attributes:** The shows themselves, up to the configured `shows_limit` / `episodes_limit` options.

```json
{
  "total_shows": 38,
  "total_episodes": 214,
  "shows": [
    {
      "show_id": "38605",
      "show_title": "Black Mirror",
      "show_images": { "poster": "https://pictures.betaseries.com/..." },
      "episode_remaining": 4,
      "episodes": [
        {
          "id": "3905073",
          "code": "S06E01",
          "title": "Joan Is Awful",
          "air_date": "2023-06-15",
          "platforms": ["Netflix"],
          "resource_url": "https://www.betaseries.com/..."
        }
      ]
    }
  ]
}
```

> `total_shows` / `total_episodes` are the endpoint's own counters and ignore the `shows_limit` / `episodes_limit` options - only the `shows` list itself is bounded by them.

With the `upcoming_media_card` integration option turned on (see
[Lovelace cards](../README.md#lovelace-cards) in the README), this sensor also carries a `data`
attribute: one item per show that has a next unseen episode, shaped for the third-party
[upcoming-media-card](https://github.com/custom-cards/upcoming-media-card). `flag` is always
`true`: everything in this list is, by definition, unwatched.

```json
{
  "data": [
    {
      "title_default": "$title",
      "line1_default": "$episode",
      "line2_default": "$number",
      "line3_default": "$date",
      "line4_default": "$empty",
      "icon": "mdi:television-classic"
    },
    {
      "airdate": "2026-05-29",
      "title": "Black Mirror",
      "episode": "Joan Is Awful",
      "number": "S06E01",
      "poster": "https://pictures.betaseries.com/...",
      "fanart": null,
      "deep_link": "https://www.betaseries.com/episode/3905073",
      "summary": "A tech CEO watches her life turned into a streaming show overnight.",
      "rating": 3.89,
      "studio": "Netflix",
      "genres": ["Science Fiction", "Drama"],
      "trailer": "https://www.youtube.com/watch?v=ZDdijwdg7s8",
      "flag": true
    }
  ]
}
```

> The first element is a template object the card itself reads (`title_default` / `line1_default`
> ... / `icon`) - never a media item. `studio` carries the streaming platforms, sorted
> alphabetically and joined with " / ", rather than an actual TV network - the card has no
> dedicated key for that. `rating` is left out (`null`) for a show you have not rated, rather than
> shown as a fake zero-star rating. `trailer` is only ever a `youtube.com` link, or `null` - the
> only trailer host BetaSeries has been observed sending in practice; any other host is left out
> rather than guessed.

#### - Suggestion of the day

**Name:** sensor.betaseries_suggestion_of_the_day
**Description:** Answers "what do I put on tonight" - one episode, picked once a day from the shows you have to catch up on. The state names the episode, worded like the calendar's events (e.g. `Black Mirror - S06E01`).
**Attributes:** Same as the airing sensors above, plus `episode_remaining`.

> A show is what gets drawn; the episode is always the oldest one you have not seen of it. The pick changes once a day, and in between only when you act on it: watch the suggested episode and it moves to the next one of that show, or to another show once you have finished it.

With the `upcoming_media_card` integration option turned on (see
[Lovelace cards](../README.md#lovelace-cards) in the README), this sensor also carries a `data`
attribute: today's suggested episode, shaped for the third-party
[upcoming-media-card](https://github.com/custom-cards/upcoming-media-card). `flag` is always
`true`: the suggestion is always an unwatched episode.

```json
{
  "data": [
    {
      "title_default": "$title",
      "line1_default": "$episode",
      "line2_default": "$number",
      "line3_default": "$date",
      "line4_default": "$empty",
      "icon": "mdi:television-classic"
    },
    {
      "airdate": "2026-05-29",
      "title": "Black Mirror",
      "episode": "Joan Is Awful",
      "number": "S06E01",
      "poster": "https://pictures.betaseries.com/...",
      "fanart": null,
      "deep_link": "https://www.betaseries.com/episode/3905073",
      "summary": "A tech CEO watches her life turned into a streaming show overnight.",
      "rating": 3.89,
      "studio": "Netflix",
      "genres": ["Science Fiction", "Drama"],
      "trailer": "https://www.youtube.com/watch?v=ZDdijwdg7s8",
      "flag": true
    }
  ]
}
```

#### - Calendar event count

**Name:** sensor.betaseries_calendar_event_count
**Description:** Diagnostic sensor. Total number of episodes currently loaded by the calendar (both watched and unwatched, across the configured months window).
**Attributes:** One `"YYYY-MM": <count>` entry per month currently loaded.

```json
{
  "2026-07": 12,
  "2026-08": 9
}
```

With the `upcoming_media_card` integration option turned on (see
[Lovelace cards](../README.md#lovelace-cards) in the README), this sensor also carries a `data`
attribute: one item per episode airing today or later, within the configured calendar window -
already-aired episodes are left out, since this lists releases rather than a backlog. No `flag`:
this is about air dates, not watch status.

```json
{
  "2026-07": 12,
  "2026-08": 9,
  "data": [
    {
      "title_default": "$title",
      "line1_default": "$episode",
      "line2_default": "$number",
      "line3_default": "$date",
      "line4_default": "$empty",
      "icon": "mdi:calendar-star"
    },
    {
      "airdate": "2026-08-20",
      "title": "Black Mirror",
      "episode": "Joan Is Awful",
      "number": "S06E01",
      "poster": "https://pictures.betaseries.com/...",
      "fanart": null,
      "deep_link": "https://www.betaseries.com/episode/3905073",
      "summary": "A tech CEO watches her life turned into a streaming show overnight.",
      "rating": 3.89,
      "studio": "Apple TV / Netflix",
      "genres": ["Science Fiction", "Drama"],
      "trailer": "https://www.youtube.com/watch?v=ZDdijwdg7s8"
    }
  ]
}
```

</details>

### Binary sensors

On/off indicators for whether you have any episode or movie left to watch.

<details>
  <summary>Display the binary sensors</summary>

| Name               | Meaning                                       | Enabled |
| ------------------ | --------------------------------------------- | ------- |
| Episodes available | On when at least one episode is left to watch | yes     |
| Movies available   | On when at least one movie is not yet watched | yes     |

> **Reports a backlog, not an arrival** - stays on permanently if you keep one. To trigger on a new episode, use **Next episode airing** or the **Planning calendar** instead.

</details>

### Calendar

The release schedule of the shows you follow, as a standard Home Assistant calendar entity.

<details>
  <summary>Display the calendar</summary>

#### - Release calendar

**Name:** calendar.betaseries_release_calendar
**Description:** One event per episode of the shows you follow, all-day, titled `<show> - <SxxEyy>` - includes both watched and unwatched episodes. The window of past/future months shown is configurable from the integration options (2 months each way by default). The "next event" points to the earliest episode airing today or later, watched or not.

</details>

### Actions via buttons

The integration caches what BetaSeries never changes - badge details, past planning months, show artwork - so it stops asking for them.

These buttons drop that cache and refresh; the only way to force such data to be re-fetched, since everything else refreshes on its own. All three are disabled by default.

<details>
  <summary>Display the actions via buttons</summary>

| Name                          | Drops                                                                          | Enabled |
| ----------------------------- | ------------------------------------------------------------------------------ | ------- |
| Clear badges cache            | The badge details, re-fetched even when the badge count hasn't changed         | no      |
| Clear planning cache          | The past months (which never change once over) and the planning's show artwork | no      |
| Clear shows to catch up cache | The show artwork of the shows to catch up on                                   | no      |

**Name:** button.betaseries_clear_badges_cache / button.betaseries_clear_planning_cache / button.betaseries_clear_shows_to_catch_up_cache

</details>

### Diagnostics

The integration entry has a **Download diagnostics** button (Settings → Devices & services → BetaSeries → the three dots on the entry).

It contains your options, each coordinator's last refresh outcome/error, the account statistics, and counts of what is loaded and cached.

> [!WARNING]
> Your API key, client secret and access token are redacted, and it deliberately holds no show or episode title - only counts.

### Actions

These actions let you mark episodes/seasons as watched, rate episodes/seasons/shows, search the BetaSeries catalog and add or remove shows from your account, directly from Home Assistant (automations, scripts, dashboards).

<details>
  <summary>Display the actions</summary>

| Action                   | Fields                                   | Notes                                                               |
| ------------------------ | ---------------------------------------- | ------------------------------------------------------------------- |
| `mark_episode_watched`   | `episode_id` (one or more)               | Marks one or more episodes as watched.                              |
| `mark_episode_unwatched` | `episode_id` (one or more)               | Fails if an episode targeted is not currently marked as watched.    |
| `rate_episode`           | `episode_id` (one or more), `note` (1-5) | An episode must already be marked as watched to be rated.           |
| `unrate_episode`         | `episode_id` (one or more)               | Removes the rating from one or more episodes.                       |
| `mark_season_watched`    | `show_id`, `season`                      | One show/season at a time (no bulk, unlike the episode actions).    |
| `mark_season_unwatched`  | `show_id`, `season`                      | One show/season at a time.                                          |
| `rate_season`            | `show_id`, `season`, `note` (1-5)        | A season must already be fully watched to be rated.                 |
| `unrate_season`          | `show_id`, `season`                      | Removes a season's rating.                                          |
| `rate_show`              | `show_id`, `note` (1-5)                  | One show at a time.                                                 |
| `unrate_show`            | `show_id`                                | Removes a show's rating.                                            |
| `add_show`               | `show_id`                                | Adds a show to your account. Fails if it is already there.          |
| `remove_show`            | `show_id`                                | Removes a show from your account. Fails if it is not there.         |
| `search_shows`           | `query`, `limit` (1-50, default 20)      | Searches the catalog. **Returns data** - needs `response_variable`. |
| `delete_token`           | none besides `config_entry`              | Destroys the account's active access token. **Irreversible.**       |

`episode_id` / `show_id` match the attributes already exposed by the sensors above (e.g. `episode_id` on **Previous/Next episode airing**), so a value copied from a dashboard card works as-is. For a show you do not follow yet, `search_shows` is where the `show_id` comes from - the sensors only ever list shows already in your account.

#### - Mark episode(s) as watched

**Name:** betaseries.mark_episode_watched
**Action:**

```yaml
action: betaseries.mark_episode_watched
data:
  config_entry: <config_entry_id>
  episode_id: "3905073,3685365"
```

#### - Rate a show

**Name:** betaseries.rate_show
**Action:**

```yaml
action: betaseries.rate_show
data:
  config_entry: <config_entry_id>
  show_id: "38605"
  note: 4
```

#### - Search the catalog

**Name:** betaseries.search_shows
**Action:**

```yaml
action: betaseries.search_shows
data:
  config_entry: <config_entry_id>
  query: "severance"
  limit: 10
response_variable: results
```

> The only action that returns data, so it is the only one requiring `response_variable`. The
> result is `{"shows": [...]}`, one entry per match, ordered by popularity. Each entry carries the
> show's `id` - what `add_show` below expects - alongside its title, year, rating, platforms and
> whether it is already `in_account`. An empty search returns `{"shows": []}`, not an error.

#### - Add a show to your account

**Name:** betaseries.add_show
**Action:**

```yaml
action: betaseries.add_show
data:
  config_entry: <config_entry_id>
  show_id: "29029"
```

> Fails if the show is already in your account - a mistake you can correct, so it surfaces as a
> validation error rather than a generic failure. `remove_show` takes exactly the same fields and
> fails symmetrically when the show is not in your account.

#### - Delete the access token

**Name:** betaseries.delete_token
**Action:**

```yaml
action: betaseries.delete_token
data:
  config_entry: <config_entry_id>
```

> Revokes the integration's own credentials, irreversibly - getting a new token always requires redoing the config flow. Triggers a reauthentication prompt right away.

</details>
