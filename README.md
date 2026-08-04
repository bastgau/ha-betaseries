# BetaSeries for Home Assistant

[![Maintainer: bastgau](https://img.shields.io/badge/maintainer-bastgau-orange?logo=github&logoColor=%23959da5&labelColor=%232d333a)](https://github.com/bastgau)
[![Made with Python](https://img.shields.io/badge/Made_with-Python-blue?style=flat&logo=python&logoColor=%23959da5&labelColor=%232d333a)](https://www.python.org/)
[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=%23959da5&labelColor=%232d333a)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bastgau/ha-betaseries?logo=github&logoColor=%23959da5&labelColor=%232d333a&color=%230e80c0)](https://github.com/bastgau/ha-betaseries/releases)
[![HACS validation](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-for-hacs.yml/badge.svg)](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-for-hacs.yml)
[![HASSFEST validation](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-with-hassfest.yml/badge.svg)](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-with-hassfest.yml)

<p align="center" width="192">
    <img src="https://raw.githubusercontent.com/bastgau/ha-betaseries/refs/heads/main/custom_components/betaseries/brand/icon.png">
</p>

## Description

This integration connects Home Assistant to your [BetaSeries](https://www.betaseries.com/) account. It exposes your viewing statistics and watchlist metrics as sensors, notifies you about upcoming episodes, provides a planning calendar, and allows you to mark episodes as watched or rate them directly from Home Assistant.

## Requirements

- Home Assistant **2026.7.0** or newer.
- A personal **BetaSeries API application** (`client_id` and `client_secret`) created at <https://www.betaseries.com/api/>

> [!WARNING]
> Your `client_id` and `client_secret` are personal credentials. Never publish or share them in GitHub repositories, forums, screenshots, logs, or configuration examples.

## Translation

The integration user interface is available in English and French.

## Installation

Before configuring the integration, create your own API application on BetaSeries to obtain a `client_id` and `client_secret`.

### Installation via HACS

1. Add this repository as a custom repository to HACS:

[![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bastgau&repository=ha-betaseries&category=Integration)

2. Use HACS to install the integration.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=betaseries)

### Manual Installation

1. Download the integration files from the GitHub repository.
2. Place the `betaseries` folder in the `custom_components` directory of Home Assistant.
3. Restart Home Assistant.
4. Set up the integration using the UI:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=betaseries)

## Configuration

During setup:

1. Enter your BetaSeries `client_id` and `client_secret`.
2. A device code is displayed.
3. Visit BetaSeries and validate the code.
4. Return to Home Assistant to complete authentication.

From the integration options, you can adjust afterwards:

- The member stats / planning polling intervals.
- How many past and future months of episodes the calendar and sensors load (2 months each way by default, 3 at most).
- How many shows, and how many episodes per show, the "Shows to catch up on" sensor lists (10 shows x 2 episodes by default).
- The preferred language for BetaSeries responses (French or English).

> [!NOTE]
> **Known limitation - the preferred language setting currently has no effect.** The integration sends
> your choice to the BetaSeries API on every request, but the API ignores it and returns content
> (genres, descriptions, error messages) in the language configured on your BetaSeries account
> instead. Change the language on [betaseries.com](https://www.betaseries.com/) if you need
> different content; the setting is kept so it starts working if BetaSeries ever fixes it.

## Entities

The most commonly used entities are:

- Episodes to watch
- Shows to catch up on
- Suggestion of the day
- Previous episode airing
- Next episode airing
- Planning calendar

### Sensor

| Name                    | Unit | Meaning                                                                                                                        | Enabled |
| ----------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------ | ------- |
| Episodes to watch       | -    | Number of episodes available to watch                                                                                          | yes     |
| Time to spend           | min  | Minutes left to watch everything pending                                                                                       | yes     |
| Progress                | %    | Overall watch progress                                                                                                         | yes     |
| Shows not started       | -    | Number of shows never started, archived ones included                                                                          | yes     |
| Movies to watch         | -    | Number of movies not yet watched                                                                                               | yes     |
| Shows in progress       | -    | Number of shows started and not yet finished                                                                                   | yes     |
| Badges                  | -    | Number of badges earned                                                                                                        | yes     |
| Shows total             | -    | Total number of shows followed, archived ones included                                                                         | yes     |
| Shows finished          | -    | Number of shows BetaSeries counts as finished, archived ones included                                                          | yes     |
| Episodes watched        | -    | Total number of episodes watched                                                                                               | yes     |
| Time on TV              | min  | Total minutes spent watching episodes                                                                                          | yes     |
| Movies total            | -    | Total number of movies watched                                                                                                 | yes     |
| XP                      | -    | Member experience points                                                                                                       | yes     |
| Streak days             | d    | Current daily streak                                                                                                           | yes     |
| Membership duration     | d    | Number of days since account creation                                                                                          | yes     |
| Episodes per month      | -    | Average number of episodes watched per month                                                                                   | yes     |
| Favorite genre          | -    | Most watched genre                                                                                                             | yes     |
| Previous episode airing | -    | Air date of the most recently aired episode, watched or not (excluding today, see below)                                       | yes     |
| Next episode airing     | -    | Air date of the next episode due to air, watched or not (including today)                                                      | yes     |
| Shows to catch up on    | -    | Number of shows with pending episodes. Detailed show and episode information is available in the entity attributes (see below) | yes     |
| Suggestion of the day   | -    | One episode to watch today, picked once a day from the shows you have to catch up on (see below)                               | yes     |
| Calendar event count    | -    | Diagnostic sensor: total number of episodes currently loaded by the calendar, broken down by month in its attributes           | no      |

**Previous / Next episode airing** are about release dates, never about what you have watched, and an episode airing today always belongs to "next". Both expose the same attributes describing the episode they point at: `episode_id`, `show_id`, `code`, `season`, `number`, `title`, `show_title`, `platforms`, `resource_url` and `show_images` (every artwork the show has). The poster is the entity picture, so both render as-is in a `picture-entity` card. How far back "previous" can see is the calendar's own window (2 months by default).

**Shows to catch up on** holds one entry per show in its `shows` attribute - `show_id`, `show_title`, `show_images`, `episode_remaining`, and an `episodes` list of `id`, `code`, `title`, `air_date`, `platforms`, `resource_url` - alongside `total_shows` and `total_episodes`, the endpoint's own counters, which ignore the two list options above.

**Suggestion of the day** answers "what do I put on tonight". Its state names an episode, worded like the calendar's events (`Black Mirror - S06E01`), and its attributes describe it - the same ones as the airing sensors, plus `episode_remaining`.

A show is what gets drawn, and the episode is always the oldest one you have not seen of it, since that is where a series is resumed. The pick changes once a day, and in between only when you act on it: watch the suggested episode and it moves to the next one of that show, or to another show once you have finished it. Watching something else leaves it alone. The draw covers the shows the **Shows to catch up on** list holds, so `shows_limit` bounds it too - raise that option if you want it to reach your whole library.

### Binary sensor

| Name               | Meaning                                       | Enabled |
| ------------------ | --------------------------------------------- | ------- |
| Episodes available | On when at least one episode is left to watch | yes     |
| Movies available   | On when at least one movie is not yet watched | yes     |

> [!NOTE]
> **These report a backlog, not an arrival.** They are on whenever the matching count is above zero, so if you keep a backlog - and most accounts do - "Episodes available" stays on permanently and never transitions. It is therefore not usable as a trigger for "a new episode came out": use the **Next episode airing** sensor, or the **Planning calendar**, both of which change when something actually airs.

### Button

The integration caches what BetaSeries never changes - badge details, past planning months, show artwork - so it stops asking for them. These three buttons drop that cache and refresh, which is the only way to get such data re-fetched - everything else refreshes on its own, so they are only useful when something looks stale.

| Name                          | Drops                                                                          | Enabled |
| ----------------------------- | ------------------------------------------------------------------------------ | ------- |
| Clean badges cache            | The badge details, re-fetched even when the badge count hasn't changed         | no      |
| Clean planning cache          | The past months (which never change once over) and the planning's show artwork | no      |
| Clean shows to catch up cache | The show artwork of the shows to catch up on                                   | no      |

### Calendar

One calendar entity ("Planning") lists episodes of the shows you follow as all-day events, titled `<show> - <SxxEyy>`, including both watched and unwatched episodes. The window of months shown (past and future) is configurable from the integration options (2 months each way by default). The calendar's own "next event" points to the earliest episode airing today or later, watched or not - like the two episode sensors, it never filters on what you have seen.

### Refresh interval

Entity values are refreshed using either the Member data refresh interval (15 minutes by default) or the Planning refresh interval (60 minutes by default), both configurable from the integration options.

### Diagnostics

The integration entry has a **Download diagnostics** button (Settings → Devices & services → BetaSeries → the three dots on the entry). It is the quickest way to report a problem: attach the file to an issue instead of describing symptoms.

It contains your options, each coordinator's last refresh outcome and error, the account statistics, and counts of what is loaded and cached - including how the planning spreads across months. Your API key, client secret and access token are redacted.

It deliberately holds **no show or episode**, only counts: the file ends up in a public issue, and what you watch is nobody else's business.

### Debugging

To show info and debug logs for the BetaSeries integration, enable logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    # Log for BetaSeries integration
    custom_components.betaseries: debug
```

> [!WARNING]
> Debug logs may contain authentication and account information. Review logs carefully before sharing them publicly.

## Actions

These actions let you mark episodes/seasons as watched or rate episodes/seasons/shows directly from Home Assistant (automations, scripts, dashboards) - covering shows and episodes only, not movies. Every action targets a BetaSeries account via a required `config_entry` field.

| Action                   | Fields                                   | Notes                                                            |
| ------------------------ | ---------------------------------------- | ---------------------------------------------------------------- |
| `mark_episode_watched`   | `episode_id` (one or more)               | Marks one or more episodes as watched.                           |
| `mark_episode_unwatched` | `episode_id` (one or more)               | Fails if an episode targeted is not currently marked as watched. |
| `rate_episode`           | `episode_id` (one or more), `note` (1-5) | An episode must already be marked as watched to be rated.        |
| `unrate_episode`         | `episode_id` (one or more)               | Removes the rating from one or more episodes.                    |
| `mark_season_watched`    | `show_id`, `season`                      | One show/season at a time (no bulk, unlike the episode actions). |
| `mark_season_unwatched`  | `show_id`, `season`                      | One show/season at a time.                                       |
| `rate_season`            | `show_id`, `season`, `note` (1-5)        | A season must already be fully watched to be rated.              |
| `unrate_season`          | `show_id`, `season`                      | Removes a season's rating.                                       |
| `rate_show`              | `show_id`, `note` (1-5)                  | One show at a time.                                              |
| `unrate_show`            | `show_id`                                | Removes a show's rating.                                         |

`episode_id`/`show_id` match the attributes already exposed by the sensors above (e.g. `episode_id` on **Previous/Next episode airing**), so a value copied from a dashboard card works as-is.

## Support & Contributions

If you encounter any issues or wish to contribute to improving this integration, feel free to open an issue or a pull request on the GitHub repository.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/bastgau)

Enjoy!
