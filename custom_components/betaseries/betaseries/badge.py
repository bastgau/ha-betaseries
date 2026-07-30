"""A badge earned by the member, as returned by GET /members/badges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class Badge:  # pylint: disable=too-many-instance-attributes
    """Represent a single badge earned by the member.

    Attributes:
        id (str): BetaSeries badge id.
        code (str): Machine-readable badge identifier (e.g. "debutant").
        name (str): Display name of the badge.
        description (str): Description of how the badge was earned.
        date (datetime): When the member earned this badge.
        height (int | None): Badge image height in pixels, if provided.
        width (int | None): Badge image width in pixels, if provided.
        level (int | None): Badge level, for tiered badges (None otherwise).

    """

    id: str
    code: str
    name: str
    description: str
    date: datetime
    height: int | None
    width: int | None
    level: int | None
