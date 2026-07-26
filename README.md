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
- **v2** - `calendar` (upcoming episodes of the shows you follow) and a `Next episode` sensor.
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

## Entities

All entities below are enabled by default and grouped under a single device per BetaSeries account (named "BetaSeries - " followed by your login). Values are refreshed at the "Member data refresh interval" (15 minutes by default) or the "Planning refresh interval" (60 minutes by default), both configured in the integration options.

### Sensor

| Name | Unit | Meaning |
|---|---|---|
| Episodes to watch | - | Number of episodes available to watch |
| Time to spend | min | Minutes left to watch everything pending |
| Progress | % | Overall watch progress |
| Shows to watch | - | Number of shows with unwatched episodes |
| Movies to watch | - | Number of movies not yet watched |
| Shows current | - | Number of shows currently being followed |
| Badges | - | Number of badges earned |
| Shows total | - | Total number of shows followed |
| Shows finished | - | Number of shows fully watched |
| Episodes watched | - | Total number of episodes watched |
| Time on TV | min | Total minutes spent watching episodes |
| Movies total | - | Total number of movies watched |
| XP | - | Member experience points |
| Streak days | d | Current daily streak |
| Member since | d | Number of days since account creation |
| Episodes per month | - | Average number of episodes watched per month |
| Favorite genre | - | Most watched genre |
| Next episode | - | Air date of the earliest episode not yet marked as watched |
| Calendar event count | - | Diagnostic sensor: total number of episodes currently loaded by the calendar, broken down by month in its attributes |

### Binary sensor

| Name | Meaning |
|---|---|
| New episode available | On when at least one episode is available to watch |
| Movies to watch available | On when at least one movie is not yet watched |

### Calendar

One calendar entity ("Planning") lists episodes of the shows you follow as all-day events, titled `<show> - <SxxEyy>`, including both watched and unwatched episodes. The window of months shown (past and future) is configurable from the integration options (2 months each way by default). The calendar's own "next event" and the `Next episode` sensor only ever point to the earliest episode not yet marked as watched.

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
