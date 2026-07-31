# BetaSeries for Home Assistant

[![Maintainer: bastgau](https://img.shields.io/badge/maintener-bastgau-orange?logo=github&logoColor=%23959da5&labelColor=%232d333a)](https://github.com/bastgau)
[![Made with Python](https://img.shields.io/badge/Made_with-Python-blue?style=flat&logo=python&logoColor=%23959da5&labelColor=%232d333a)](https://www.python.org/)
[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=%23959da5&labelColor=%232d333a)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bastgau/ha-betaseries?logo=github&logoColor=%23959da5&labelColor=%232d333a&color=%230e80c0)](https://github.com/bastgau/ha-betaseries/releases)
[![HACS validation](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-for-hacs.yml/badge.svg)](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-for-hacs.yml)
[![HASSFEST validation](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-with-hassfest.yml/badge.svg)](https://github.com/bastgau/ha-betaseries/actions/workflows/validate-with-hassfest.yml)

<p align="center" width="100%">
    <img src="https://brands.home-assistant.io/_/betaseries/logo.png">
</p>

## Description

This integration connects Home Assistant to your [BetaSeries](https://www.betaseries.com/) account. It exposes your viewing stats and to-watch counts as sensors, tells you when new episodes are available, shows your upcoming episodes as a calendar, and (in a later version) will let you mark episodes watched or rate them.

It is delivered in three stages:

- **v1** - `sensor` (account stats: episodes to watch, time to spend, progress, badges, etc.) and `binary_sensor` (a new episode / a movie to watch is available). Includes authentication.
- **v2** - `calendar` (upcoming episodes of the shows you follow) and the episode sensors.
- **v3** - `services` (mark an episode/season watched, rate an episode/show).

## Requirements

- Home Assistant **2026.7.0** or newer.
- A personal **BetaSeries API key** (`client_id` + `client_secret`). Each user must create their own key at <https://www.betaseries.com/api/> - a shared key cannot be embedded in a public repository. Setup uses the OAuth **device flow**: Home Assistant shows you a code to enter on the BetaSeries website; your password is never typed into Home Assistant.

## Translation

The integration is translated into:

- English
- French

## Installation

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

During setup you will be asked for your BetaSeries `client_id` and `client_secret`, then shown a device code to validate on the BetaSeries website. From the integration options, you can adjust afterwards:

- The member stats / planning polling intervals.
- How many past and future months of episodes the calendar and sensors load (2 months each way by default).
- How many shows, and how many episodes per show, the "Watch list" sensor holds (10 shows x 2 episodes by default).
- The preferred language for BetaSeries responses (French or English).

> [!NOTE]
> **Known limitation - the preferred language setting currently has no effect.** The integration sends
> your choice to the BetaSeries API on every request, but the API ignores it and returns content
> (genres, descriptions, error messages) in the language configured on your BetaSeries account
> instead. This was verified against several endpoints. Change the language on
> [betaseries.com](https://www.betaseries.com/) itself if you need different content. The setting is
> kept so it starts working automatically if BetaSeries fixes the behaviour on their side.

## Entities

All entities below are enabled by default and grouped under a single device per BetaSeries account (named "BetaSeries - " followed by your login). Values are refreshed at the "Member data refresh interval" (15 minutes by default) or the "Planning refresh interval" (60 minutes by default), both configured in the integration options.

### Sensor

| Name | Unit | Meaning |
|---|---|---|
| Episodes to watch | - | Number of episodes available to watch |
| Time to spend | min | Minutes left to watch everything pending |
| Progress | % | Overall watch progress |
| Shows not started | - | Number of shows never started, archived ones included |
| Movies to watch | - | Number of movies not yet watched |
| Shows in progress | - | Number of shows started and not yet finished |
| Badges | - | Number of badges earned |
| Shows total | - | Total number of shows followed, archived ones included |
| Shows finished | - | Number of shows BetaSeries counts as finished, archived ones included |
| Episodes watched | - | Total number of episodes watched |
| Time on TV | min | Total minutes spent watching episodes |
| Movies total | - | Total number of movies watched |
| XP | - | Member experience points |
| Streak days | d | Current daily streak |
| Membership duration | d | Number of days since account creation |
| Episodes per month | - | Average number of episodes watched per month |
| Favorite genre | - | Most watched genre |
| Latest unwatched episode | - | Air date of the most recently aired episode not yet marked as watched (excluding today, see below) |
| Next episode airing | - | Air date of the next episode due to air, watched or not (including today) |
| Watch list | - | Episodes left to watch, with the first few shows listed in its attributes (see below) |
| Calendar event count | - | Diagnostic sensor: total number of episodes currently loaded by the calendar, broken down by month in its attributes |

BetaSeries only ever tells which day an episode airs, never at what time, so each sensor pins its timestamp to the end of the day it cannot be wrong about: "next episode airing" uses 23:59:59 and "latest unwatched episode" uses midnight. Home Assistant's relative display ("in 3 days", "2 days ago") then always agrees with what the sensor announces. For the same reason an episode airing today belongs to "next episode airing" until the day is over - claiming it is already watchable would be a guess - so the two sensors never point at the same episode.

Both expose the same attributes, describing the episode they point at: `episode_id`, `show_id`, `code`, `season`, `number`, `title`, `show_title`, `platforms` and `resource_url`. `episode_id` and `show_id` are the identifiers BetaSeries actions will target, so a dashboard card can act on the episode the sensor points at.

They also carry the show's poster as their picture, so they render nicely in a `picture-entity` card. The `show_images` attribute holds every artwork the show has (`poster`, `banner`, `box`, `show`, `clearlogo`) so a card can use a different one - a banner for a wide layout, a clearlogo to overlay. Artwork the show doesn't have is left out of that attribute, and shows with no artwork at all simply get no picture.

The **Watch list** sensor is what a `markdown` card can render to show what to watch next, with no custom component involved. Its `shows` attribute holds one entry per show - `show_id`, `show_title`, `show_images`, `episode_remaining` (episodes left for that show) and an `episodes` list of `id`, `code`, `title`, `air_date`, `platforms` and `resource_url` - alongside `total_shows` and `total_episodes`, which count the whole watch list rather than the listed part. How much it lists is set by the two options above; the totals ignore them.

It is deliberately a separate entity: its list would otherwise weigh on the plain statistics sensors above every time they change.

> [!NOTE]
> **It is not written to your database.** Home Assistant normally records an entity's attributes alongside every state it stores, which for this list would mean several kilobytes per change. The integration declares the `shows` attribute as unrecorded, so nothing needs configuring on your side: the state and the two totals keep their history, the list itself is never written. It stays fully readable from cards, templates and automations, which read the live state rather than the database.
>
> The same applies to the `badges` attribute of the **Badges** sensor and to `show_images` on the episode sensors. If you would rather drop an entity from your history entirely, exclude it from the `recorder` as usual, or disable it from its settings in the UI.

### Binary sensor

| Name | Meaning |
|---|---|
| New episode available | On when at least one episode is available to watch |
| Movies to watch available | On when at least one movie is not yet watched |

### Button

The integration caches what BetaSeries never changes - badge details, past planning months, show artwork - so it stops asking for them. These three buttons drop that cache and refresh, which is the only way to get such data re-fetched. They are **disabled by default**: everything else refreshes on its own, so these are only useful when something looks stale.

| Name | Drops |
|---|---|
| Clean badges cache | The badge details, re-fetched even when the badge count hasn't changed |
| Clean planning cache | The past months (which never change once over) and the planning's show artwork |
| Clean watch list cache | The watch list's show artwork |

### Calendar

One calendar entity ("Planning") lists episodes of the shows you follow as all-day events, titled `<show> - <SxxEyy>`, including both watched and unwatched episodes. The window of months shown (past and future) is configurable from the integration options (2 months each way by default). The calendar's own "next event" points to the earliest episode not yet marked as watched.

## Troubleshooting

## Debugging

To show info and debug logs for the BetaSeries integration, enable logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    # Log for BetaSeries integration
    custom_components.betaseries: debug
```

Logs are not scrubbed of sensitive information, so review what you share before posting it.

## Support & Contributions

If you encounter any issues or wish to contribute to improving this integration, feel free to open an issue or a pull request on the GitHub repository.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/bastgau)

Enjoy!
