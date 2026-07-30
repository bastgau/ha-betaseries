"""Full member data, as returned by GET /members/infos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .collection_badge import CollectionBadge

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
        badges (CollectionBadge): The member's earned badges, empty until fetched
            via Client.fetch_badges() (GET /members/infos doesn't return them,
            only their count in stats.badges - see MemberCoordinator).

    """

    identity: MemberIdentity
    stats: MemberStats
    badges: CollectionBadge = field(default_factory=lambda: CollectionBadge(()))
