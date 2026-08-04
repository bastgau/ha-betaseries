"""A member's id and login, as returned by GET /members/infos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberIdentity:
    """Represent a member's id and login.

    Used on its own by Auth once the device flow completes (before the full
    MemberData is needed), and as part of MemberData once fetched via
    Client.fetch_member_data().

    Attributes:
        id (str): BetaSeries member id.
        login (str): BetaSeries member login (username).

    """

    id: str
    login: str
