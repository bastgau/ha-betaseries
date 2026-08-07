"""Tests for the BetaSeries config flow (method menu, device flow, login/password).

HA's FlowManager never loops synchronously through SHOW_PROGRESS steps: the
first async_configure call always returns SHOW_PROGRESS (with a progress_task
registered), and a done_callback on that task schedules a follow-up
async_configure once it completes. Since our progress_task (poll_for_token)
resolves near-instantly with a mocked Auth, the test helper below
awaits hass.async_block_till_done() then re-calls async_configure(flow_id)
to retrieve the flow's actual terminal (or next) result.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.betaseries.betaseries.device_code import DeviceCodeData
from custom_components.betaseries.betaseries.exceptions import (
    AuthError,
    AuthTimeoutError,
)
from custom_components.betaseries.betaseries.member_identity import MemberIdentity
from custom_components.betaseries.const import CONF_LOCALE, CONF_MEMBER_SCAN_INTERVAL, DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

DEVICE_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret"}
# Credentials submitted via the device_credentials form (includes client_secret).
DEVICE_STEP_INPUT = {**DEVICE_INPUT, CONF_LOCALE: "fr"}
# What's actually stored in entry.data (client_secret is not persisted).
SAVED_DATA = {CONF_API_KEY: "test-api-key"}

PASSWORD_INPUT = {CONF_API_KEY: "test-api-key", CONF_USERNAME: "test_user", CONF_PASSWORD: "hunter2"}
# Credentials submitted via the password_credentials form.
PASSWORD_STEP_INPUT = {**PASSWORD_INPUT, CONF_LOCALE: "fr"}

DEVICE_CODE_DATA = DeviceCodeData(
    device_code="device-code",
    user_code="XYZ789",
    verification_url="https://www.betaseries.com/device",
    expires_in=1800,
    interval=5,
)


async def _open_menu(hass: HomeAssistant) -> ConfigFlowResult:
    """Init the flow and return the "user" method-choice menu."""
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def _choose_device(hass: HomeAssistant, flow_id: str) -> ConfigFlowResult:
    """Pick the device flow option from the "user" menu."""
    return await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "device_credentials"})


async def _choose_password(hass: HomeAssistant, flow_id: str) -> ConfigFlowResult:
    """Pick the login/password option from the "user" menu."""
    return await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "password_credentials"})


async def _start_device_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Init the flow, pick device auth, submit its credentials, and let the progress task settle."""
    result = await _open_menu(hass)
    result = await _choose_device(hass, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)

    if result["type"] is FlowResultType.SHOW_PROGRESS:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    return result


async def test_full_flow_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Complete the device flow end-to-end and create the config entry."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "token123"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="test_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test_user"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        "access_token": "token123",
    }
    assert result["options"] == {CONF_LOCALE: "fr"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_shows_menu_initially(hass: HomeAssistant) -> None:
    """Show the authentication method menu on the first call."""
    result = await _open_menu(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["device_credentials", "password_credentials"]


async def test_device_credentials_step_shows_form(hass: HomeAssistant) -> None:
    """Show the device flow credentials form after picking it from the menu, with no errors."""
    result = await _open_menu(hass)
    result = await _choose_device(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_credentials"
    assert result["errors"] is None


async def test_password_credentials_step_shows_form(hass: HomeAssistant) -> None:
    """Show the login/password credentials form after picking it from the menu, with no errors."""
    result = await _open_menu(hass)
    result = await _choose_password(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_credentials"
    assert result["errors"] is None


async def test_device_credentials_request_device_code_failure(hass: HomeAssistant) -> None:
    """Show the retry/switch-method menu if requesting the device code fails.

    A menu rather than the credentials form redisplayed with an inline error:
    see async_step_device_credentials_error's docstring for why (a stuck flow
    resumed later, e.g. via reauth, must not strand the user on a bare form).
    """
    mock_auth = AsyncMock()
    mock_auth.request_device_code.side_effect = AuthError("boom")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "device_credentials_error"
    assert result["menu_options"] == ["device_credentials", "user"]


async def test_device_credentials_error_retry_reshows_the_form(hass: HomeAssistant) -> None:
    """Show a clean device_credentials form again after picking "Try again"."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.side_effect = AuthError("boom")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "device_credentials"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_credentials"
    assert result["errors"] is None


async def test_device_credentials_error_switch_method_shows_menu(hass: HomeAssistant) -> None:
    """Show the method menu again after picking "Choose a different method"."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.side_effect = AuthError("boom")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "user"})

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_device_code_timeout(hass: HomeAssistant) -> None:
    """Move to the timeout step if the device code expires before validation."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = AuthTimeoutError("expired")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "timeout"


async def test_device_code_still_pending_shows_progress(hass: HomeAssistant) -> None:
    """Show the progress screen while the device code has not been validated yet."""
    still_waiting = asyncio.Event()

    async def _poll_for_token(*_args: object, **_kwargs: object) -> str:
        await still_waiting.wait()
        return "token123"

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = _poll_for_token
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="test_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_device(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "device_code"
        assert result["progress_action"] == "wait_for_device"
        assert result["description_placeholders"] == {
            "url": DEVICE_CODE_DATA.verification_url,
            "code": DEVICE_CODE_DATA.user_code,
        }

        still_waiting.set()
        await hass.async_block_till_done()
        await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_device_code_repoll_while_still_pending(hass: HomeAssistant) -> None:
    """Show progress again (not a new task) if polled again before it settles."""
    still_waiting = asyncio.Event()

    async def _poll_for_token(*_args: object, **_kwargs: object) -> str:
        await still_waiting.wait()
        return "token123"

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = _poll_for_token
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="test_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_device(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # Re-poll before the login task has settled: still the same progress,
        # not a second poll_for_token call (login_task is reused, not recreated).
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "device_code"
        assert result["description_placeholders"] == {
            "url": DEVICE_CODE_DATA.verification_url,
            "code": DEVICE_CODE_DATA.user_code,
        }
        assert mock_auth.poll_for_token.call_count == 1

        still_waiting.set()
        await hass.async_block_till_done()
        await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_device_code_definitive_error_aborts(hass: HomeAssistant) -> None:
    """Abort the flow if the device flow fails definitively while polling."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = AuthError("invalid client_secret")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_finish_login_failure_aborts(hass: HomeAssistant) -> None:
    """Abort the flow if fetching the member identity fails."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "token123"
    mock_auth.fetch_member_identity.side_effect = AuthError("boom")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_timeout_step_retries(hass: HomeAssistant) -> None:
    """Show the method menu again when the timeout form is submitted.

    Not the device credentials form directly: a timeout is exactly the
    symptom of the Android issue the menu step exists for, so the user gets a
    chance to switch to login/password instead of just retrying.
    """
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = AuthTimeoutError("expired")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)
        assert result["step_id"] == "timeout"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_already_configured_aborts(hass: HomeAssistant) -> None:
    """Abort if a config entry with the same member id already exists."""
    MockConfigEntry(domain=DOMAIN, unique_id="42").add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "token123"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="test_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,  # noqa: ARG001
) -> None:
    """Update the existing entry's token on a successful reauth, preserving its other options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**SAVED_DATA, "access_token": "old-token"},
        options={CONF_MEMBER_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "new-token"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="test_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await _choose_device(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["access_token"] == "new-token"
    # The locale submitted during reauth is applied, without clobbering
    # unrelated options already set (async_update_reload_and_abort's
    # `options=` fully replaces, so config_flow.py must merge manually).
    assert entry.options == {CONF_MEMBER_SCAN_INTERVAL: 30, CONF_LOCALE: "fr"}


async def test_reauth_flow_wrong_account_aborts(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,  # noqa: ARG001
) -> None:
    """Abort without touching the entry if reauth completes with a different member id."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", data={**SAVED_DATA, "access_token": "old-token"})
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "new-token"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="99", login="a_different_user")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await _choose_device(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == "42"
    assert entry.data["access_token"] == "old-token"


async def test_device_credentials_rejects_invalid_locale(hass: HomeAssistant) -> None:
    """Reject a locale outside the fr/en SelectSelector options, on the device credentials form."""
    result = await _open_menu(hass)
    result = await _choose_device(hass, result["flow_id"])

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(result["flow_id"], {**DEVICE_INPUT, CONF_LOCALE: "es"})


async def test_reauth_flow_defaults_locale_to_entrys_current_option(hass: HomeAssistant) -> None:
    """Pre-fill the reauth form's locale with the entry's current option, not DEFAULT_LOCALE."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**SAVED_DATA, "access_token": "old-token"},
        options={CONF_LOCALE: "en"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _choose_device(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_credentials"
    # Not a dict comprehension over every key: api_key/client_secret have no
    # default (vol.UNDEFINED, not callable), unlike the options-flow schema.
    assert result["data_schema"] is not None
    locale_key = next(key for key in result["data_schema"].schema if key.schema == CONF_LOCALE)
    assert locale_key.default() == "en"


async def test_network_failure_shows_cannot_connect(hass: HomeAssistant) -> None:
    """Show the retry/switch-method menu when BetaSeries is unreachable.

    Regression test: the flow only ever caught AuthError, so a raw
    aiohttp.ClientError from the device code request escaped the step
    entirely and Home Assistant reported "Unknown error occurred" with a
    traceback. Auth now wraps transport failures into AuthError, so the
    unreachable case reaches the same menu as any other failure.
    """
    mock_auth = AsyncMock()
    mock_auth.request_device_code.side_effect = AuthError("Could not reach BetaSeries")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_device(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_STEP_INPUT)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "device_credentials_error"


async def test_password_flow_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Complete the login/password flow end-to-end, with no device code involved."""
    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.return_value = ("token123", MemberIdentity(id="42", login="test_user"))

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test_user"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        "access_token": "token123",
    }
    assert result["options"] == {CONF_LOCALE: "fr"}
    assert len(mock_setup_entry.mock_calls) == 1
    mock_auth.authenticate_with_password.assert_awaited_once_with("test_user", "hunter2")


async def test_password_flow_invalid_credentials(hass: HomeAssistant) -> None:
    """Show the retry/switch-method menu if the login/password is rejected."""
    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.side_effect = AuthError("bad credentials")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "password_credentials_error"
    assert result["menu_options"] == ["password_credentials", "user"]


async def test_password_credentials_error_retry_reshows_the_form(hass: HomeAssistant) -> None:
    """Show a clean password_credentials form again after picking "Try again"."""
    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.side_effect = AuthError("bad credentials")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "password_credentials"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_credentials"
    assert result["errors"] is None


async def test_password_credentials_error_switch_method_shows_menu(hass: HomeAssistant) -> None:
    """Show the method menu again after picking "Choose a different method"."""
    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.side_effect = AuthError("bad credentials")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "user"})

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_password_flow_already_configured_aborts(hass: HomeAssistant) -> None:
    """Abort if a config entry with the same member id already exists."""
    MockConfigEntry(domain=DOMAIN, unique_id="42").add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.return_value = ("token123", MemberIdentity(id="42", login="test_user"))

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _open_menu(hass)
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_password_credentials_rejects_invalid_locale(hass: HomeAssistant) -> None:
    """Reject a locale outside the fr/en SelectSelector options, on the password credentials form."""
    result = await _open_menu(hass)
    result = await _choose_password(hass, result["flow_id"])

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(result["flow_id"], {**PASSWORD_INPUT, CONF_LOCALE: "es"})


async def test_password_reauth_flow_success(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,  # noqa: ARG001
) -> None:
    """Reauthenticate an existing entry through login/password instead of the device flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        data={**SAVED_DATA, "access_token": "old-token"},
        options={CONF_MEMBER_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.return_value = ("new-token", MemberIdentity(id="42", login="test_user"))

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["access_token"] == "new-token"
    assert entry.options == {CONF_MEMBER_SCAN_INTERVAL: 30, CONF_LOCALE: "fr"}


async def test_password_reauth_flow_wrong_account_aborts(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,  # noqa: ARG001
) -> None:
    """Abort without touching the entry if password reauth completes with a different member id."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", data={**SAVED_DATA, "access_token": "old-token"})
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.authenticate_with_password.return_value = ("new-token", MemberIdentity(id="99", login="other_user"))

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await _choose_password(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], PASSWORD_STEP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == "42"
    assert entry.data["access_token"] == "old-token"
