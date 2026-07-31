"""Config flow for the BetaSeries integration (OAuth device flow).

Modeled after homeassistant.components.tado.config_flow, with two
differences documented in CLAUDE.md §3:
- BetaSeries requires an initial form (api_key + client_secret) before the
  device code can be requested, unlike Tado which uses baked-in credentials.
- The expires_in guard rail is implemented in the betaseries sub-package
  (Auth), not here, since there is no underlying library to do it
  for us.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,  # pyright: ignore[reportUnknownVariableType]
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,  # pyright: ignore[reportUnknownVariableType]
    SelectSelectorConfig,
    SelectSelectorMode,
)

# Aliased: bare "Auth" would be ambiguous next to homeassistant.auth in this file.
from .betaseries import (
    Auth as BetaSeriesAuth,
    AuthError as BetaSeriesAuthError,
    AuthTimeoutError as BetaSeriesAuthTimeoutError,
    DeviceCodeData,
)
from .const import (
    CONF_EPISODES_LIMIT,
    CONF_EPISODES_SCAN_INTERVAL,
    CONF_LOCALE,
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    CONF_SHOWS_LIMIT,
    DEFAULT_EPISODES_LIMIT,
    DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES,
    DEFAULT_LOCALE,
    DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES,
    DEFAULT_PLANNING_MONTHS_AHEAD,
    DEFAULT_PLANNING_MONTHS_BEHIND,
    DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES,
    DEFAULT_SHOWS_LIMIT,
    DOMAIN,
    MAX_EPISODES_LIMIT,
    MAX_EPISODES_SCAN_INTERVAL_MINUTES,
    MAX_MEMBER_SCAN_INTERVAL_MINUTES,
    MAX_PLANNING_MONTHS_AHEAD,
    MAX_PLANNING_MONTHS_BEHIND,
    MAX_PLANNING_SCAN_INTERVAL_MINUTES,
    MAX_SHOWS_LIMIT,
    MIN_EPISODES_LIMIT,
    MIN_EPISODES_SCAN_INTERVAL_MINUTES,
    MIN_MEMBER_SCAN_INTERVAL_MINUTES,
    MIN_PLANNING_MONTHS_AHEAD,
    MIN_PLANNING_MONTHS_BEHIND,
    MIN_PLANNING_SCAN_INTERVAL_MINUTES,
    MIN_SHOWS_LIMIT,
    SUPPORTED_LOCALES,
)

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry


def _user_data_schema(default_locale: str) -> vol.Schema:
    """Build the credentials + locale form schema for the "user" step.

    Args:
        default_locale (str): Locale pre-selected in the form (DEFAULT_LOCALE, or the entry's current option during reauth).

    Returns:
        vol.Schema: The "user" step's form schema.

    """
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_CLIENT_SECRET): str,
            vol.Required(CONF_LOCALE, default=default_locale): SelectSelector(
                SelectSelectorConfig(
                    options=SUPPORTED_LOCALES, mode=SelectSelectorMode.DROPDOWN, translation_key=CONF_LOCALE
                )
            ),
        }
    )


# The options form groups its fields into one section per coordinator. These
# keys only ever exist in the form: _flatten_sections() unwraps them before the
# options are stored, so entry.options stays the flat mapping the coordinators
# read (and pre-existing entries need no migration).
SECTION_MEMBER = "member"
SECTION_PLANNING = "planning"
SECTION_EPISODES = "episodes"

_OPTION_SECTIONS = (SECTION_MEMBER, SECTION_PLANNING, SECTION_EPISODES)


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Merge the options form's sections back into a flat mapping.

    Home Assistant returns a section's fields nested under the section's own
    key; the coordinators expect them alongside the ungrouped ones.

    Args:
        user_input (dict[str, Any]): The submitted form data, with its sections nested.

    Returns:
        dict[str, Any]: The same values, flattened.

    """
    flattened = {key: value for key, value in user_input.items() if key not in _OPTION_SECTIONS}
    for name in _OPTION_SECTIONS:
        flattened.update(user_input.get(name, {}))
    return flattened


class BetaSeriesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BetaSeries.

    Attributes:
        login_task (asyncio.Task[str] | None): Task polling for the access token.
        auth (BetaSeriesAuth | None): Auth client created once credentials are known.
        device_code_data (DeviceCodeData | None): Device code obtained from BetaSeries.
        access_token (str | None): Access token obtained once the device code is validated.
        api_key (str): BetaSeries API key (client_id) entered by the user.
        client_secret (str): BetaSeries API client secret entered by the user.
        locale (str): Preferred response language ("fr" or "en") selected by the user.

    """

    login_task: asyncio.Task[str] | None = None
    auth: BetaSeriesAuth | None = None
    device_code_data: DeviceCodeData | None = None
    access_token: str | None = None
    api_key: str = ""
    client_secret: str = ""
    locale: str = DEFAULT_LOCALE

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BetaSeriesOptionsFlow:  # noqa: ARG004
        """Get the options flow for this handler.

        Args:
            config_entry (ConfigEntry): Unused; self.config_entry is auto-populated by the flow manager.

        Returns:
            BetaSeriesOptionsFlow: The options flow handling the scan interval settings.

        """
        return BetaSeriesOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the BetaSeries API credentials before starting the device flow.

        Args:
            user_input (dict[str, Any] | None): Form data, or None to show the form.

        Returns:
            ConfigFlowResult: The next flow step.

        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            self.client_secret = user_input[CONF_CLIENT_SECRET]
            self.locale = user_input[CONF_LOCALE]
            self.auth = BetaSeriesAuth(async_get_clientsession(self.hass), self.api_key, self.client_secret)
            try:
                self.device_code_data = await self.auth.request_device_code()
            except BetaSeriesAuthError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_device_code()

        default_locale = DEFAULT_LOCALE
        if self.source == SOURCE_REAUTH:
            default_locale = self._get_reauth_entry().options.get(CONF_LOCALE, DEFAULT_LOCALE)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_data_schema(default_locale),
            errors=errors,
        )

    async def async_step_device_code(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Poll for the access token while showing the user_code to the user.

        Args:
            user_input (dict[str, Any] | None): Unused; HA re-invokes this step while polling.

        Returns:
            ConfigFlowResult: The progress screen, or the next step once done.

        Raises:
            RuntimeError: If reached before async_step_user set up the auth client.

        """
        if self.auth is None or self.device_code_data is None:
            # Cannot happen: this step is only reached from async_step_user,
            # which always sets both before returning here.
            raise RuntimeError  # pragma: no cover

        if self.login_task is None:
            self.login_task = self.hass.async_create_task(
                self.auth.poll_for_token(
                    self.device_code_data.device_code,
                    self.device_code_data.expires_in,
                    self.device_code_data.interval,
                )
            )

        if self.login_task.done():
            exception = self.login_task.exception()
            if isinstance(exception, BetaSeriesAuthTimeoutError):
                return self.async_show_progress_done(next_step_id="timeout")
            if exception is not None:
                return self.async_abort(reason="cannot_connect")

            self.access_token = self.login_task.result()
            return self.async_show_progress_done(next_step_id="finish_login")

        return self.async_show_progress(
            step_id="device_code",
            progress_action="wait_for_device",
            description_placeholders={
                "url": self.device_code_data.verification_url,
                "code": self.device_code_data.user_code,
            },
            progress_task=self.login_task,
        )

    async def async_step_finish_login(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fetch the member identity and create (or update) the config entry.

        Args:
            user_input (dict[str, Any] | None): Unused; this step never shows a form.

        Returns:
            ConfigFlowResult: The created/updated entry, or an abort result.

        Raises:
            RuntimeError: If reached before async_step_device_code set up the token.

        """
        if self.auth is None or self.access_token is None:
            # Cannot happen: this step is only reached from async_step_device_code,
            # which always sets both before returning here.
            raise RuntimeError  # pragma: no cover

        try:
            identity = await self.auth.fetch_member_identity(self.access_token)
        except BetaSeriesAuthError:
            return self.async_abort(reason="cannot_connect")

        data = {
            CONF_API_KEY: self.api_key,
            CONF_CLIENT_SECRET: self.client_secret,
            "access_token": self.access_token,
        }

        await self.async_set_unique_id(identity.id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry,
                data_updates=data,
                options={**reauth_entry.options, CONF_LOCALE: self.locale},
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=identity.login, data=data, options={CONF_LOCALE: self.locale})

    async def async_step_timeout(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user retry after the device code expired.

        HA's FlowManager.async_configure loops on SHOW_PROGRESS_DONE, re-passing
        the *original* user_input from async_step_user (never None, since our
        flow has a real credentials form). So user_input can't be used here to
        tell "just arrived from progress" apart from "form submitted" -- unlike
        Tado, whose device flow has no credentials form and so never hits this.
        self.login_task is used instead: it is only non-None on the first visit.

        Args:
            user_input (dict[str, Any] | None): Unused; see note above.

        Returns:
            ConfigFlowResult: The retry form, or a fresh async_step_user call.

        """
        if self.login_task is not None:
            self.login_task = None
            self.device_code_data = None
            return self.async_show_form(step_id="timeout")

        return await self.async_step_user()

    async def async_step_reauth(  # pylint: disable=unused-argument
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when the stored token is rejected.

        Args:
            entry_data (Mapping[str, Any]): Unused; data of the entry being reauthenticated.

        Returns:
            ConfigFlowResult: The reauth confirmation step.

        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm the user wants to restart the device flow to reauthenticate.

        Args:
            user_input (dict[str, Any] | None): Form data, or None to show the form.

        Returns:
            ConfigFlowResult: The confirmation form, or a fresh async_step_user call.

        """
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user()


class BetaSeriesOptionsFlow(OptionsFlowWithReload):
    """Handle the scan interval, months window and locale options (see CLAUDE.md §6, arbitrage #4)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user configure the scan intervals, months window and locale.

        The form groups its fields into one collapsed section per coordinator,
        but the submitted values are flattened back before being stored: the
        options stay a flat mapping, so the coordinators keep reading them
        with a plain options.get(KEY, DEFAULT).

        Args:
            user_input (dict[str, Any] | None): Form data, or None to show the form.

        Returns:
            ConfigFlowResult: The created options entry, or the options form.

        """
        if user_input is not None:
            return self.async_create_entry(data=_flatten_sections(user_input))

        options = self.config_entry.options
        options_schema = vol.Schema(
            {
                vol.Required(SECTION_MEMBER): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_MEMBER_SCAN_INTERVAL,
                                default=options.get(CONF_MEMBER_SCAN_INTERVAL, DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_MEMBER_SCAN_INTERVAL_MINUTES,
                                    max=MAX_MEMBER_SCAN_INTERVAL_MINUTES,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(SECTION_PLANNING): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_PLANNING_SCAN_INTERVAL,
                                default=options.get(
                                    CONF_PLANNING_SCAN_INTERVAL, DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES
                                ),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_PLANNING_SCAN_INTERVAL_MINUTES,
                                    max=MAX_PLANNING_SCAN_INTERVAL_MINUTES,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                            vol.Required(
                                CONF_PLANNING_MONTHS_BEHIND,
                                default=options.get(CONF_PLANNING_MONTHS_BEHIND, DEFAULT_PLANNING_MONTHS_BEHIND),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_PLANNING_MONTHS_BEHIND,
                                    max=MAX_PLANNING_MONTHS_BEHIND,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                            vol.Required(
                                CONF_PLANNING_MONTHS_AHEAD,
                                default=options.get(CONF_PLANNING_MONTHS_AHEAD, DEFAULT_PLANNING_MONTHS_AHEAD),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_PLANNING_MONTHS_AHEAD,
                                    max=MAX_PLANNING_MONTHS_AHEAD,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(SECTION_EPISODES): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_EPISODES_SCAN_INTERVAL,
                                default=options.get(
                                    CONF_EPISODES_SCAN_INTERVAL, DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES
                                ),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_EPISODES_SCAN_INTERVAL_MINUTES,
                                    max=MAX_EPISODES_SCAN_INTERVAL_MINUTES,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                            vol.Required(
                                CONF_SHOWS_LIMIT,
                                default=options.get(CONF_SHOWS_LIMIT, DEFAULT_SHOWS_LIMIT),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_SHOWS_LIMIT, max=MAX_SHOWS_LIMIT, mode=NumberSelectorMode.BOX
                                )
                            ),
                            vol.Required(
                                CONF_EPISODES_LIMIT,
                                default=options.get(CONF_EPISODES_LIMIT, DEFAULT_EPISODES_LIMIT),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=MIN_EPISODES_LIMIT, max=MAX_EPISODES_LIMIT, mode=NumberSelectorMode.BOX
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(
                    CONF_LOCALE,
                    default=options.get(CONF_LOCALE, DEFAULT_LOCALE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=SUPPORTED_LOCALES, mode=SelectSelectorMode.DROPDOWN, translation_key=CONF_LOCALE
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
