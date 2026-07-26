"""Full member data, as returned by GET /members/infos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .member_identity import MemberIdentity
    from .member_stats import MemberStats


@dataclass(frozen=True)
class MemberData:
    """Represent the member data returned by GET /members/infos.

    Source for all v1 sensors and binary_sensors (see CLAUDE.md §5).

    Attributes:
        identity (MemberIdentity): The member's id and login.
        stats (MemberStats): The member's viewing statistics, including xp.

    """

    identity: MemberIdentity
    stats: MemberStats
