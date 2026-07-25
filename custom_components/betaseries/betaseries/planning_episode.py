"""A single upcoming episode, as returned by GET /planning/member."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True)
class PlanningEpisode:  # pylint: disable=too-many-instance-attributes
    """Represent one episode from the member's planning.

    Flattened from the nested API payload (show/user/platform_links) for
    simpler consumption by calendar.py/sensor.py. See CLAUDE.md §4.

    Attributes:
        id (str): BetaSeries episode id.
        show_id (str): BetaSeries show id.
        show_title (str): Title of the show this episode belongs to.
        season (int): Season number.
        episode (int): Episode number within the season.
        code (str): Season/episode code (e.g. "S03E04").
        title (str): Episode title.
        air_date (date): Date the episode airs/aired.
        seen (bool): Whether the member has already watched this episode.
        platforms (tuple[str, ...]): Streaming platforms this episode is available on.
        resource_url (str): Link to the episode's BetaSeries page.

    """

    id: str
    show_id: str
    show_title: str
    season: int
    episode: int
    code: str
    title: str
    air_date: date
    seen: bool
    platforms: tuple[str, ...]
    resource_url: str
