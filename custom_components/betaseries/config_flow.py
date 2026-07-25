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

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .betaseries import (
    Auth,
    AuthError,
    AuthTimeoutError,
    DeviceCodeData,
)
from .const import DOMAIN

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Mapping

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_CLIENT_SECRET): str,
    }
)


class BetaSeriesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BetaSeries.

    Attributes:
        login_task (asyncio.Task[str] | None): Task polling for the access token.
        auth (Auth | None): Auth client created once credentials are known.
        device_code_data (DeviceCodeData | None): Device code obtained from BetaSeries.
        access_token (str | None): Access token obtained once the device code is validated.
        api_key (str): BetaSeries API key (client_id) entered by the user.
        client_secret (str): BetaSeries API client secret entered by the user.

    """

    login_task: asyncio.Task[str] | None = None
    auth: Auth | None = None
    device_code_data: DeviceCodeData | None = None
    access_token: str | None = None
    api_key: str = ""
    client_secret: str = ""

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
            self.auth = Auth(async_get_clientsession(self.hass), self.api_key, self.client_secret)
            try:
                self.device_code_data = await self.auth.request_device_code()
            except AuthError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_device_code()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
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
            if isinstance(exception, AuthTimeoutError):
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
        except AuthError:
            return self.async_abort(reason="cannot_connect")

        data = {
            CONF_API_KEY: self.api_key,
            CONF_CLIENT_SECRET: self.client_secret,
            "access_token": self.access_token,
        }

        await self.async_set_unique_id(identity.id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=identity.login, data=data)

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
