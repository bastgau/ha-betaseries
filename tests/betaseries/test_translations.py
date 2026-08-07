"""Tests tying the config flow's translation keys to the files that carry them.

Nothing else does. A key present in one language and absent from another (or
missing from strings.json's own step/menu definitions) surfaces as an
untranslated string for some users only, or a raw key shown verbatim - the
kind of gap that no amount of exercising the flow in tests will reveal.

The device and password credentials forms used to hand Home Assistant an
`errors["base"] = "..."` key on a rejected api_key/client_secret or
login/password. That mechanism is gone: both now redirect to a small
"retry or choose a different method" menu instead (see
async_step_device_credentials_error/async_step_password_credentials_error in
config_flow.py) - a stuck/abandoned flow resumed later (e.g. via reauth) must
not strand the user on a bare form with no way back. Nothing in config_flow.py
raises an `errors[...]` key anymore, so there is nothing left here to scan for
that shape specifically; test_translations_match_the_reference_keys below
still catches a menu/step definition missing from one language.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

INTEGRATION_PATH = Path(__file__).parents[2] / "custom_components" / "betaseries"

TRANSLATION_FILES = (
    INTEGRATION_PATH / "strings.json",
    INTEGRATION_PATH / "translations" / "en.json",
    INTEGRATION_PATH / "translations" / "fr.json",
)


def _load(path: Path) -> dict[str, Any]:
    """Read one translation file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _key_paths(node: object, prefix: str = "") -> set[str]:
    """Flatten a decoded translation file into dotted key paths."""
    if not isinstance(node, dict):
        return {prefix}
    # isinstance() only narrows to dict[Unknown, Unknown]; these files are
    # decoded JSON objects, so the keys are strings and the values anything.
    mapping = cast("dict[str, object]", node)
    return {path for key, value in mapping.items() for path in _key_paths(value, f"{prefix}.{key}" if prefix else key)}


@pytest.mark.parametrize("path", TRANSLATION_FILES[1:], ids=lambda path: path.name)
def test_translations_match_the_reference_keys(path: Path) -> None:
    """Keep every translation file structurally identical to strings.json.

    A key present in one language and absent from another surfaces as an
    untranslated string for some users only - the kind of gap that no amount
    of exercising the flow in tests will reveal.
    """
    reference = _key_paths(_load(TRANSLATION_FILES[0]))
    candidate = _key_paths(_load(path))

    assert candidate == reference, (
        f"{path.name} diverges from strings.json - "
        f"missing: {sorted(reference - candidate)}, unexpected: {sorted(candidate - reference)}"
    )
