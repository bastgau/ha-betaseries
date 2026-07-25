"""Minimal member identity, used only to close the config flow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberIdentity:
    """Represent a minimal member identity, used only to close the config flow.

    The full member data (stats, etc.) is fetched by Client,
    added in a later milestone alongside the data coordinator.

    Attributes:
        id (str): BetaSeries member id.
        login (str): BetaSeries member login (username).

    """

    id: str
    login: str
