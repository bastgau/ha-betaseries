"""Tests tying the config flow's translation keys to the files that carry them.

Nothing else does. A flow hands Home Assistant a *key* - `errors["base"] =
"cannot_connect"` - and the frontend resolves it against
`component.betaseries.config.error.<key>`. If that entry is missing the flow
still behaves correctly, every other test still passes, and the user is the
one who finds out: the form comes back with nothing useful where the reason
should be.

That is exactly how config.error went missing here in the first place. The
device flow was modelled on `tado`, which has no credentials form and so never
shows a form error and never needed the section; the credentials form this
integration adds on top does (see CLAUDE.md §3).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, cast

import pytest

INTEGRATION_PATH = Path(__file__).parents[2] / "custom_components" / "betaseries"

TRANSLATION_FILES = (
    INTEGRATION_PATH / "strings.json",
    INTEGRATION_PATH / "translations" / "en.json",
    INTEGRATION_PATH / "translations" / "fr.json",
)

# Matches `errors["base"] = "cannot_connect"` and any sibling the flow grows.
_ERROR_ASSIGNMENT = re.compile(r"""errors\[["'](?P<field>\w+)["']\]\s*=\s*["'](?P<key>\w+)["']""")


def _load(path: Path) -> dict[str, Any]:
    """Read one translation file.

    Args:
        path (Path): The file to read.

    Returns:
        dict[str, Any]: Its decoded contents.

    """
    return json.loads(path.read_text(encoding="utf-8"))


def _key_paths(node: object, prefix: str = "") -> set[str]:
    """Flatten a decoded translation file into dotted key paths.

    Args:
        node (object): The current node, a mapping or a leaf string.
        prefix (str): Dotted path of the node's parent.

    Returns:
        set[str]: Every leaf's dotted path.

    """
    if not isinstance(node, dict):
        return {prefix}
    # isinstance() only narrows to dict[Unknown, Unknown]; these files are
    # decoded JSON objects, so the keys are strings and the values anything.
    mapping = cast("dict[str, object]", node)
    return {path for key, value in mapping.items() for path in _key_paths(value, f"{prefix}.{key}" if prefix else key)}


def test_every_config_flow_error_key_is_translated() -> None:
    """Give every error the flow can raise a string in every language.

    Scans config_flow.py rather than listing the keys here, so a new
    `errors[...] = "..."` is covered the day it is written instead of the day
    someone remembers this test exists.
    """
    source = (INTEGRATION_PATH / "config_flow.py").read_text(encoding="utf-8")
    raised = {match["key"] for match in _ERROR_ASSIGNMENT.finditer(source)}

    # Guards the regex itself: if it silently stops matching, the loop below
    # would pass over an empty set and assert nothing at all.
    assert raised, "no errors[...] assignment found - has config_flow.py changed shape?"

    for path in TRANSLATION_FILES:
        translated = _load(path).get("config", {}).get("error", {})
        missing = raised - translated.keys()
        assert not missing, f"{path.name} is missing config.error entries: {sorted(missing)}"


@pytest.mark.parametrize("path", TRANSLATION_FILES[1:], ids=lambda path: path.name)
def test_translations_match_the_reference_keys(path: Path) -> None:
    """Keep every translation file structurally identical to strings.json.

    A key present in one language and absent from another surfaces as an
    untranslated string for some users only - the kind of gap that no amount
    of exercising the flow in tests will reveal.

    Args:
        path (Path): The translation file to compare against strings.json.

    """
    reference = _key_paths(_load(TRANSLATION_FILES[0]))
    candidate = _key_paths(_load(path))

    assert candidate == reference, (
        f"{path.name} diverges from strings.json - "
        f"missing: {sorted(reference - candidate)}, unexpected: {sorted(candidate - reference)}"
    )
