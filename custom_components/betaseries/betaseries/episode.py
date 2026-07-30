"""A single episode, as returned by GET /planning/member."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from .client import Client
    from .show import Show


@dataclass(frozen=True)
class Episode:  # pylint: disable=too-many-instance-attributes
    """Represent a single episode, together with the show it belongs to.

    See CLAUDE.md §4.

    Attributes:
        id (str): BetaSeries episode id.
        season (int): Season number.
        number (int): Episode number within the season.
        code (str): Season/episode code (e.g. "S03E04").
        title (str): Episode title.
        description (str): Episode summary, as returned by the API (may be empty).
        air_date (date): Date the episode airs/aired.
        seen (bool): Whether the member has already watched this episode.
        platforms (tuple[str, ...]): Streaming platforms this episode is available on.
        resource_url (str): Link to the episode's BetaSeries page.
        show (Show): The show this episode belongs to.

    """

    id: str
    season: int
    number: int
    code: str
    title: str
    description: str
    air_date: date
    seen: bool
    platforms: tuple[str, ...]
    resource_url: str
    show: Show

    async def fetch_show(self, client: Client) -> Episode:
        """Fetch this episode's show, and return this episode with it enriched.

        Args:
            client (Client): The BetaSeries API client to fetch the show with.

        Returns:
            Episode: A new Episode with `show` enriched (additional_information populated).

        """
        shows = await client.fetch_shows([self.show.id])
        show = shows.for_show(self.show.id) or self.show
        return replace(self, show=show)
