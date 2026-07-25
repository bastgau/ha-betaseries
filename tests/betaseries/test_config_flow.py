"""Tests for the BetaSeries config flow (device flow).

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
from custom_components.betaseries.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

USER_INPUT = {CONF_API_KEY: "test-api-key", CONF_CLIENT_SECRET: "test-client-secret"}

DEVICE_CODE_DATA = DeviceCodeData(
    device_code="device-code",
    user_code="XYZ789",
    verification_url="https://www.betaseries.com/device",
    expires_in=1800,
    interval=5,
)


async def _start_device_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Init the flow, submit the credentials form, and let the progress task settle.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.

    Returns:
        ConfigFlowResult: The flow's result once the progress task has resolved.

    """
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    if result["type"] is FlowResultType.SHOW_PROGRESS:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    return result


async def test_full_flow_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Complete the device flow end-to-end and create the config entry.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        mock_setup_entry (AsyncMock): Patched async_setup_entry, isolating this
            test from the real setup (coordinator, platforms).

    """
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "token123"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="bastgau")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "bastgau"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_CLIENT_SECRET: "test-client-secret",
        "access_token": "token123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_shows_form_initially(hass: HomeAssistant) -> None:
    """Show the credentials form on the first call, with no errors."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_request_device_code_failure(hass: HomeAssistant) -> None:
    """Show the form again with an error if requesting the device code fails."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.side_effect = AuthError("boom")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


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
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="bastgau")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

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
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="bastgau")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
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
    """Restart the user step when the timeout form is submitted."""
    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.side_effect = AuthTimeoutError("expired")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)
        assert result["step_id"] == "timeout"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_already_configured_aborts(hass: HomeAssistant) -> None:
    """Abort if a config entry with the same member id already exists."""
    MockConfigEntry(domain=DOMAIN, unique_id="42").add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "token123"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="bastgau")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await _start_device_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,  # noqa: ARG001
) -> None:
    """Update the existing entry's token on a successful reauth.

    Args:
        hass (HomeAssistant): The Home Assistant test instance.
        mock_setup_entry (AsyncMock): Patched async_setup_entry, isolating this
            test from the real setup triggered by the reauth reload.

    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id="42", data={**USER_INPUT, "access_token": "old-token"})
    entry.add_to_hass(hass)

    mock_auth = AsyncMock()
    mock_auth.request_device_code.return_value = DEVICE_CODE_DATA
    mock_auth.poll_for_token.return_value = "new-token"
    mock_auth.fetch_member_identity.return_value = MemberIdentity(id="42", login="bastgau")

    with patch("custom_components.betaseries.config_flow.BetaSeriesAuth", return_value=mock_auth):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["access_token"] == "new-token"
