"""Config flow for the BetaSeries integration (device flow, or login/password).

Modeled after homeassistant.components.tado.config_flow, with differences
documented in CLAUDE.md §3:
- BetaSeries requires an initial form (api_key + client_secret) before the
  device code can be requested, unlike Tado which uses baked-in credentials.
- The expires_in guard rail is implemented in the betaseries sub-package
  (Auth), not here, since there is no underlying library to do it
  for us.
- A first "user" menu step lets the user pick between the device flow and a
  login/password alternative (Auth.authenticate_with_password) - added
  because the device flow can get stuck on some Android setups waiting for
  the browser to hand control back to the Home Assistant app. Both paths
  converge on _async_create_or_update_entry() once an access token and
  member identity are known.
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
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,  # pyright: ignore[reportUnknownVariableType]
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
    MemberIdentity,
)
from .const import (
    API_URL,
    CONF_EPISODES_LIMIT,
    CONF_EPISODES_SCAN_INTERVAL,
    CONF_LOCALE,
    CONF_MEMBER_SCAN_INTERVAL,
    CONF_PLANNING_MONTHS_AHEAD,
    CONF_PLANNING_MONTHS_BEHIND,
    CONF_PLANNING_SCAN_INTERVAL,
    CONF_SHOWS_LIMIT,
    CONF_UPCOMING_MEDIA_CARD,
    DEFAULT_EPISODES_LIMIT,
    DEFAULT_EPISODES_SCAN_INTERVAL_MINUTES,
    DEFAULT_LOCALE,
    DEFAULT_MEMBER_SCAN_INTERVAL_MINUTES,
    DEFAULT_PLANNING_MONTHS_AHEAD,
    DEFAULT_PLANNING_MONTHS_BEHIND,
    DEFAULT_PLANNING_SCAN_INTERVAL_MINUTES,
    DEFAULT_SHOWS_LIMIT,
    DEFAULT_UPCOMING_MEDIA_CARD,
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


def _locale_schema_entry(default_locale: str) -> dict[vol.Marker, Any]:
    """Build the locale field shared by every credentials form.

    Args:
        default_locale (str): Locale pre-selected in the form (DEFAULT_LOCALE, or the entry's current option during reauth).

    Returns:
        dict[vol.Marker, Any]: A single-entry schema fragment, meant to be spread into a vol.Schema dict.

    """
    return {
        vol.Required(CONF_LOCALE, default=default_locale): SelectSelector(
            SelectSelectorConfig(
                options=SUPPORTED_LOCALES, mode=SelectSelectorMode.DROPDOWN, translation_key=CONF_LOCALE
            )
        )
    }


def _device_data_schema(default_locale: str) -> vol.Schema:
    """Build the api_key + client_secret + locale form schema for the "device_credentials" step.

    Args:
        default_locale (str): Locale pre-selected in the form (DEFAULT_LOCALE, or the entry's current option during reauth).

    Returns:
        vol.Schema: The "device_credentials" step's form schema.

    """
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_CLIENT_SECRET): str,
            **_locale_schema_entry(default_locale),
        }
    )


def _password_data_schema(default_locale: str) -> vol.Schema:
    """Build the api_key + login + password + locale form schema for the "password_credentials" step.

    Args:
        default_locale (str): Locale pre-selected in the form (DEFAULT_LOCALE, or the entry's current option during reauth).

    Returns:
        vol.Schema: The "password_credentials" step's form schema.

    """
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            **_locale_schema_entry(default_locale),
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

    async def async_step_user(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick between the device flow and login/password.

        Two independent trade-offs, both documented in CLAUDE.md §3: the
        device flow's client_secret can only be rotated by asking BetaSeries
        support to delete and recreate the API application, and it can get
        stuck on some Android setups. The login/password alternative returns
        a token BetaSeries never revokes, not even on a password change. This
        step only offers the choice; it is made deliberately by the user, not
        assumed here.

        Args:
            user_input (dict[str, Any] | None): Unused; this step never shows a form.

        Returns:
            ConfigFlowResult: The authentication method menu.

        """
        return self.async_show_menu(step_id="user", menu_options=["device_credentials", "password_credentials"])

    def _default_locale(self) -> str:
        """Return the locale to pre-select on a credentials form.

        Returns:
            str: The reauthenticated entry's current locale option, or DEFAULT_LOCALE for a new entry.

        """
        if self.source == SOURCE_REAUTH:
            return self._get_reauth_entry().options.get(CONF_LOCALE, DEFAULT_LOCALE)
        return DEFAULT_LOCALE

    async def async_step_device_credentials(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the BetaSeries API credentials before starting the device flow.

        Args:
            user_input (dict[str, Any] | None): Form data, or None to show the form.

        Returns:
            ConfigFlowResult: The next flow step.

        """
        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            self.client_secret = user_input[CONF_CLIENT_SECRET]
            self.locale = user_input[CONF_LOCALE]
            self.auth = BetaSeriesAuth(async_get_clientsession(self.hass), self.api_key, self.client_secret)
            try:
                self.device_code_data = await self.auth.request_device_code()
            except BetaSeriesAuthError:
                return await self.async_step_device_credentials_error()
            return await self.async_step_device_code()

        return self.async_show_form(
            step_id="device_credentials",
            data_schema=_device_data_schema(self._default_locale()),
            description_placeholders={
                "betaserie_api_url": API_URL,
            },
        )

    async def async_step_device_credentials_error(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to retry the device credentials or switch method, after a rejected api_key/client_secret.

        A real menu rather than redisplaying the credentials form with an
        inline error: a stuck/abandoned flow reopened later (e.g. via reauth,
        which resumes an in-progress flow instead of starting fresh) would
        otherwise strand the user on that same form with no way back to the
        method choice - this menu is always the answer either way.

        Args:
            user_input (dict[str, Any] | None): Unused; this step never shows a form, only a menu.

        Returns:
            ConfigFlowResult: The retry/switch-method choice.

        """
        return self.async_show_menu(step_id="device_credentials_error", menu_options=["device_credentials", "user"])

    async def async_step_password_credentials(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the BetaSeries API key and account login/password, and authenticate directly.

        Unlike the device flow this is a single blocking request: no code to
        validate on the BetaSeries website, no polling. See CLAUDE.md §3 for
        the trade-off this carries (the returned token is never revoked, not
        even by a password change) - already surfaced to the user on the
        "user" menu step, not repeated as a warning here.

        Args:
            user_input (dict[str, Any] | None): Form data, or None to show the form.

        Returns:
            ConfigFlowResult: The created/updated entry, or the credentials form.

        """
        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            self.locale = user_input[CONF_LOCALE]
            auth = BetaSeriesAuth(async_get_clientsession(self.hass), self.api_key)
            try:
                self.access_token, identity = await auth.authenticate_with_password(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except BetaSeriesAuthError:
                return await self.async_step_password_credentials_error()
            return await self._async_create_or_update_entry(identity)

        return self.async_show_form(
            step_id="password_credentials",
            data_schema=_password_data_schema(self._default_locale()),
            description_placeholders={
                "betaserie_api_url": API_URL,
            },
        )

    async def async_step_password_credentials_error(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to retry the login/password or switch method, after rejected credentials.

        See async_step_device_credentials_error's docstring - same reasoning,
        mirrored for the login/password path.

        Args:
            user_input (dict[str, Any] | None): Unused; this step never shows a form, only a menu.

        Returns:
            ConfigFlowResult: The retry/switch-method choice.

        """
        return self.async_show_menu(step_id="password_credentials_error", menu_options=["password_credentials", "user"])

    async def async_step_device_code(  # pylint: disable=unused-argument
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Poll for the access token while showing the user_code to the user.

        Args:
            user_input (dict[str, Any] | None): Unused; HA re-invokes this step while polling.

        Returns:
            ConfigFlowResult: The progress screen, or the next step once done.

        Raises:
            RuntimeError: If reached before async_step_device_credentials set up the auth client.

        """
        if self.auth is None or self.device_code_data is None:
            # Cannot happen: this step is only reached from async_step_device_credentials,
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

        Only reached from the device flow: the login/password path already
        gets the member identity in its own response and goes straight to
        _async_create_or_update_entry() instead (see async_step_password_credentials).

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

        return await self._async_create_or_update_entry(identity)

    async def _async_create_or_update_entry(self, identity: MemberIdentity) -> ConfigFlowResult:
        """Create the entry (or update it during reauth) from a known access token and member identity.

        Shared by both authentication paths once each has its own token and
        identity: the device flow via async_step_finish_login, the
        login/password flow directly from async_step_password_credentials.

        Args:
            identity (MemberIdentity): The authenticated member's id and login.

        Returns:
            ConfigFlowResult: The created/updated entry, or an abort result (unique id conflict).

        Raises:
            RuntimeError: If reached before an access token was obtained.

        """
        if self.access_token is None:
            # Cannot happen: both callers set it before calling this method.
            raise RuntimeError  # pragma: no cover

        data = {
            CONF_API_KEY: self.api_key,
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
        the *original* user_input from async_step_device_credentials (never
        None, since our flow has a real credentials form). So user_input can't
        be used here to tell "just arrived from progress" apart from "form
        submitted" -- unlike Tado, whose device flow has no credentials form
        and so never hits this. self.login_task is used instead: it is only
        non-None on the first visit.

        Retrying re-shows the method menu rather than jumping straight back
        into the device credentials form: a timeout here is exactly the
        symptom of the Android issue this whole menu step exists for, so the
        user gets a chance to switch to login/password instead of retrying
        the same thing.

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
                            vol.Required(
                                CONF_UPCOMING_MEDIA_CARD,
                                default=options.get(CONF_UPCOMING_MEDIA_CARD, DEFAULT_UPCOMING_MEDIA_CARD),
                            ): BooleanSelector(),
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
