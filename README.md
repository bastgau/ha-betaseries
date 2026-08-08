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
- A personal **BetaSeries API application** (`client_id` and `client_secret`) created at <https://www.betaseries.com/api/>. The `client_secret` is only required for the device code authentication method below; the login/password method only needs the `client_id`.

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

During setup, choose one of two authentication methods:

- **Device code (recommended)**:
  1. Enter your BetaSeries `client_id` and `client_secret`.
  2. A device code is displayed.
  3. Visit BetaSeries and validate the code.
  4. Return to Home Assistant to complete authentication.
- **Login and password**: enter your BetaSeries `client_id`, plus your BetaSeries account login and password. This is a single step, no code to validate - offered because the device code flow can get stuck in some mobile app setups (e.g. Android) waiting for the browser to hand control back to Home Assistant.

> [!WARNING]
> Unlike the device code, BetaSeries never revokes the token returned by this method - not even if you later change your account password. Prefer the device code method unless it doesn't work for you.

From the integration options, you can adjust afterwards:

- The member stats / planning polling intervals.
- How many past and future months of episodes the calendar and sensors load (2 months each way by default; up to 24 months back, 2 months ahead).
- How many shows, and how many episodes per show, the "Shows to catch up on" sensor lists (10 shows x 2 episodes by default).
- Whether the "Shows to catch up on" and "Calendar event count" sensors expose a `data` attribute for the [upcoming-media-card](https://github.com/custom-cards/upcoming-media-card) Lovelace card (off by default). See [Lovelace cards](#lovelace-cards) below.
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

See **[Entities & Services](docs/guide-explained-entities.md)** for the full list of sensors, binary sensors, the calendar and its attributes, the diagnostic cache-purge buttons, and the available actions.

### Refresh interval

Entity values are refreshed using either the Member data refresh interval (15 minutes by default) or the Planning refresh interval (60 minutes by default), both configurable from the integration options.

### Diagnostics

The integration entry has a **Download diagnostics** button (Settings → Devices & services → BetaSeries → the three dots on the entry). It is the quickest way to report a problem: attach the file to an issue instead of describing symptoms.

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

## Lovelace cards

### upcoming-media-card

The **Shows to catch up on** and **Calendar event count** sensors can feed the third-party
[upcoming-media-card](https://github.com/custom-cards/upcoming-media-card) Lovelace card directly,
behind the `upcoming_media_card` integration option (Watch list section, off by default). Turning
it on enables it on both sensors at once - there is a single option, not one per sensor.

```yaml
type: custom:upcoming-media-card
entity: sensor.betaseries_shows_to_catch_up_on
title: To catch up on
image_style: fanart
```

Only the `$title`, `$episode`, `$number`, `$date`, `$day`, `$time`, `$rating`, `$studio` and
`$empty` placeholders resolve to something in `line1_text` / `line2_text` / etc.

See **[Entities & Services](docs/guide-explained-entities.md)** for the exact shape of the `data`
attribute each sensor exposes once the option is on.

## Troubleshooting

### Setup stuck on "waiting for confirmation" in the Android companion app

Adding the integration from the **Home Assistant Android companion app** can get stuck on the
device-code confirmation screen even after validating the code on betaseries.com - sometimes
resurfacing an "authentication process timed out" popup that loops back to the same screen.
Restarting the flow only issues a new device code from scratch instead of resuming.

**Workaround**: set up the integration from a web browser (desktop or mobile) instead of the
Android companion app - it works normally afterward, once the config entry exists. Switching to
the **login and password** authentication method (see [Configuration](#configuration)) can also
be a solution.

## Support & Contributions

If you encounter any issues or wish to contribute to improving this integration, feel free to open an issue or a pull request on the GitHub repository.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/bastgau)

Enjoy!
