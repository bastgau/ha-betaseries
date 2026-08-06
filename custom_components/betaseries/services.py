"""Actions for the BetaSeries integration (see CLAUDE.md §8)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import service
from homeassistant.helpers.selector import (
    ConfigEntrySelector,  # pyright: ignore[reportUnknownVariableType]
    NumberSelector,  # pyright: ignore[reportUnknownVariableType]
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,  # pyright: ignore[reportUnknownVariableType]
)

from .betaseries import AuthError, Error, NotWatchedError
from .const import (
    ATTR_CONFIG_ENTRY,
    ATTR_EPISODE_ID,
    ATTR_NOTE,
    ATTR_SEASON,
    ATTR_SHOW_ID,
    DOMAIN,
    SERVICE_DELETE_TOKEN,
    SERVICE_MARK_EPISODE_UNWATCHED,
    SERVICE_MARK_EPISODE_WATCHED,
    SERVICE_MARK_SEASON_UNWATCHED,
    SERVICE_MARK_SEASON_WATCHED,
    SERVICE_RATE_EPISODE,
    SERVICE_RATE_SEASON,
    SERVICE_RATE_SHOW,
    SERVICE_UNRATE_EPISODE,
    SERVICE_UNRATE_SEASON,
    SERVICE_UNRATE_SHOW,
)

if TYPE_CHECKING:
    from .coordinator import BetaSeriesConfigEntry

_NOTE_SELECTOR = NumberSelector(  # pyright: ignore[reportUnknownVariableType]
    NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)
)

_EPISODE_IDS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_EPISODE_ID): TextSelector(),
    }
)

_RATE_EPISODES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_EPISODE_ID): TextSelector(),
        vol.Required(ATTR_NOTE): _NOTE_SELECTOR,
    }
)

_SEASON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_SHOW_ID): TextSelector(),
        vol.Required(ATTR_SEASON): NumberSelector(NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)),
    }
)

_RATE_SEASON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_SHOW_ID): TextSelector(),
        vol.Required(ATTR_SEASON): NumberSelector(NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)),
        vol.Required(ATTR_NOTE): _NOTE_SELECTOR,
    }
)

_SHOW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_SHOW_ID): TextSelector(),
    }
)

_CONFIG_ENTRY_ONLY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    }
)

_RATE_SHOW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_SHOW_ID): TextSelector(),
        vol.Required(ATTR_NOTE): _NOTE_SELECTOR,
    }
)


def _get_entry(hass: HomeAssistant, call: ServiceCall) -> BetaSeriesConfigEntry:
    """Resolve the targeted config entry from a service call.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        call (ServiceCall): The service call, carrying ATTR_CONFIG_ENTRY.

    Returns:
        BetaSeriesConfigEntry: The resolved config entry.

    """
    return service.async_get_config_entry(hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY])


def _episode_ids(call: ServiceCall) -> list[str]:
    """Split ATTR_EPISODE_ID's comma-separated string into individual ids.

    A plain (non-multiple) text field, not HA's "multiple" text selector: the
    latter's frontend loses input focus on every keystroke in the Developer
    Tools > Actions form, reported unusable by the user. A single field typed
    as "1001,1002" also matches the wire format the API itself expects
    (verified via Bruno), so no translation is needed either way.

    Args:
        call (ServiceCall): The service call, carrying ATTR_EPISODE_ID.

    Returns:
        list[str]: The individual episode ids, whitespace trimmed.

    """
    return [episode_id.strip() for episode_id in call.data[ATTR_EPISODE_ID].split(",") if episode_id.strip()]


def _raise_for_client_error(err: Exception) -> None:
    """Translate a client Error/AuthError/NotWatchedError into an HA-facing exception.

    NotWatchedError is the one case the caller can act on (rate/unwatch the
    prerequisite first), hence ServiceValidationError; AuthError and any other
    Error are HomeAssistantError - a rejected token is not something the
    caller can fix by changing their service call, and the entry's normal
    reauth flow (triggered by the next scheduled coordinator refresh) handles
    it separately (see CLAUDE.md §3).

    Args:
        err (Exception): The exception raised by the client call.

    Returns:
        None

    Raises:
        ServiceValidationError: If the target is not marked as watched.
        HomeAssistantError: For any other client failure.

    """
    if isinstance(err, NotWatchedError):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_watched") from err
    if isinstance(err, AuthError):
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auth_error") from err
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="service_call_failed",
        translation_placeholders={"error": str(err)},
    ) from err


async def _mark_episode_watched(call: ServiceCall) -> None:
    """Mark one or more episodes as watched, then refresh the affected coordinators.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.mark_episodes_watched(_episode_ids(call))
    except Error as err:
        _raise_for_client_error(err)
    else:
        await entry.runtime_data.member.async_request_refresh()
        await entry.runtime_data.watch_list.async_request_refresh()


async def _mark_episode_unwatched(call: ServiceCall) -> None:
    """Remove the watched mark from one or more episodes, then refresh the affected coordinators.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.mark_episodes_unwatched(_episode_ids(call))
    except Error as err:
        _raise_for_client_error(err)
    else:
        await entry.runtime_data.member.async_request_refresh()
        await entry.runtime_data.watch_list.async_request_refresh()


async def _rate_episode(call: ServiceCall) -> None:
    """Rate one or more episodes.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.rate_episodes(_episode_ids(call), call.data[ATTR_NOTE])
    except Error as err:
        _raise_for_client_error(err)


async def _unrate_episode(call: ServiceCall) -> None:
    """Remove the rating from one or more episodes.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.unrate_episodes(_episode_ids(call))
    except Error as err:
        _raise_for_client_error(err)


async def _mark_season_watched(call: ServiceCall) -> None:
    """Mark every episode of a season as watched, then refresh the affected coordinators.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.mark_season_watched(call.data[ATTR_SHOW_ID], call.data[ATTR_SEASON])
    except Error as err:
        _raise_for_client_error(err)
    else:
        await entry.runtime_data.member.async_request_refresh()
        await entry.runtime_data.watch_list.async_request_refresh()


async def _mark_season_unwatched(call: ServiceCall) -> None:
    """Remove the watched mark from every episode of a season, then refresh the affected coordinators.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.mark_season_unwatched(call.data[ATTR_SHOW_ID], call.data[ATTR_SEASON])
    except Error as err:
        _raise_for_client_error(err)
    else:
        await entry.runtime_data.member.async_request_refresh()
        await entry.runtime_data.watch_list.async_request_refresh()


async def _rate_season(call: ServiceCall) -> None:
    """Rate a season.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.rate_season(
            call.data[ATTR_SHOW_ID], call.data[ATTR_SEASON], call.data[ATTR_NOTE]
        )
    except Error as err:
        _raise_for_client_error(err)


async def _unrate_season(call: ServiceCall) -> None:
    """Remove a season's rating.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.unrate_season(call.data[ATTR_SHOW_ID], call.data[ATTR_SEASON])
    except Error as err:
        _raise_for_client_error(err)


async def _rate_show(call: ServiceCall) -> None:
    """Rate a show.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.rate_show(call.data[ATTR_SHOW_ID], call.data[ATTR_NOTE])
    except Error as err:
        _raise_for_client_error(err)


async def _unrate_show(call: ServiceCall) -> None:
    """Remove a show's rating.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.unrate_show(call.data[ATTR_SHOW_ID])
    except Error as err:
        _raise_for_client_error(err)


async def _delete_token(call: ServiceCall) -> None:
    """Destroy the account's active access token, then trigger reauthentication.

    Irreversible (see Client.delete_token) - there is no corresponding
    "create_token" service, since obtaining a new one always requires the
    config flow (device flow or login/password, CLAUDE.md §3), not just an
    API call. The immediate refresh below is what actually surfaces the
    reauth prompt right away: MemberCoordinator's own AuthError handling
    raises ConfigEntryAuthFailed, which DataUpdateCoordinator turns into a
    reauth flow without propagating back here, so this call still succeeds.

    Args:
        call (ServiceCall): The service call data.

    Returns:
        None

    """
    entry = _get_entry(call.hass, call)
    try:
        await entry.runtime_data.member.client.delete_token()
    except Error as err:
        _raise_for_client_error(err)
    else:
        await entry.runtime_data.member.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the BetaSeries services, once per Home Assistant run.

    Registered at the domain level (not per config entry), same as
    `homeassistant.components.habitica.services` (CLAUDE.md §10): one BetaSeries
    account is enough to use every service, and multiple accounts share the
    same registration, picking the target via ATTR_CONFIG_ENTRY.

    Args:
        hass (HomeAssistant): The Home Assistant instance.

    Returns:
        None

    """
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_EPISODE_WATCHED, _mark_episode_watched, schema=_EPISODE_IDS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_EPISODE_UNWATCHED, _mark_episode_unwatched, schema=_EPISODE_IDS_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RATE_EPISODE, _rate_episode, schema=_RATE_EPISODES_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UNRATE_EPISODE, _unrate_episode, schema=_EPISODE_IDS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MARK_SEASON_WATCHED, _mark_season_watched, schema=_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MARK_SEASON_UNWATCHED, _mark_season_unwatched, schema=_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RATE_SEASON, _rate_season, schema=_RATE_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UNRATE_SEASON, _unrate_season, schema=_SEASON_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RATE_SHOW, _rate_show, schema=_RATE_SHOW_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UNRATE_SHOW, _unrate_show, schema=_SHOW_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_TOKEN, _delete_token, schema=_CONFIG_ENTRY_ONLY_SCHEMA)
