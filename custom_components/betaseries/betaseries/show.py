"""A show, as referenced by a planning episode."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client
    from .collection_episode import CollectionEpisode
    from .show_additional_information import ShowAdditionalInformation


@dataclass(frozen=True)
class Show:
    """Represent a show.

    Attributes:
        id (str): BetaSeries show id.
        title (str): Title of the show this episode belongs to.
        description (str | None): The show's synopsis, if the source payload's show sub-object has one (None otherwise).
        slug (str | None): The show's URL slug, if the source payload's show sub-object has one (None otherwise).
        additional_information (ShowAdditionalInformation | None): Richer show details, if fetched via Client.fetch_shows() (None otherwise).
        episodes (CollectionEpisode | None): This show's episodes, if fetched via fetch_episodes() (None otherwise).

    """

    id: str
    title: str
    description: str | None = None
    slug: str | None = None
    additional_information: ShowAdditionalInformation | None = None
    episodes: CollectionEpisode | None = None

    @property
    def resource_url(self) -> str | None:
        """Return this show's BetaSeries page, derived from its slug.

        Verified pattern (bruno/Shows/display.bru): `resource_url` for a show
        with slug "achtsam-morden" is "https://www.betaseries.com/serie/achtsam-morden".

        Returns:
            str | None: The show's page URL, or None if the slug is unknown.

        """
        return f"https://www.betaseries.com/serie/{self.slug}" if self.slug else None

    async def fetch_episodes(self, client: Client) -> Show:
        """Fetch every episode of this show, and return this show with them attached.

        Args:
            client (Client): The BetaSeries API client to fetch episodes with.

        Returns:
            Show: A new Show with `episodes` populated.

        """
        episodes = await client.fetch_show_episodes(self.id)
        return replace(self, episodes=episodes)

    async def fetch_additional_information(self, client: Client) -> Show:
        """Fetch this show's full details, and return the freshly-fetched Show.

        Same request as Episode.fetch_show() makes for its embedded show -
        besides `additional_information`, this also refreshes `description`/
        `slug` from that same response: there's no reason to keep an older,
        lighter value around once /shows/display's is available.

        Args:
            client (Client): The BetaSeries API client to fetch shows with.

        Returns:
            Show: The freshly-fetched Show, or this one unchanged if it's unexpectedly absent from the response.

        """
        shows = await client.fetch_shows([self.id])
        return shows.for_show(self.id) or self
