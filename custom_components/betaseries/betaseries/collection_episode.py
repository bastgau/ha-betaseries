"""A collection of the member's planning episodes, as returned by GET /planning/member."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .client import Client
    from .episode import Episode


class CollectionEpisode:
    """Wrap the member's episodes, with convenience access to the shows they belong to.

    Attributes:
        _episodes (tuple[Episode, ...]): The wrapped episodes.

    """

    def __init__(self, episodes: tuple[Episode, ...]) -> None:
        """Initialize the collection.

        Args:
            episodes (tuple[Episode, ...]): The episodes to wrap.

        """
        self._episodes = episodes

    def __iter__(self) -> Iterator[Episode]:
        """Iterate over the wrapped episodes.

        Returns:
            Iterator[Episode]: An iterator over the episodes.

        """
        return iter(self._episodes)

    def __len__(self) -> int:
        """Return the number of wrapped episodes.

        Returns:
            int: The number of episodes.

        """
        return len(self._episodes)

    @property
    def show_ids(self) -> frozenset[str]:
        """Return the unique show ids referenced by these episodes.

        Returns:
            frozenset[str]: The unique show ids.

        """
        return frozenset(episode.show.id for episode in self._episodes)

    async def fetch_shows(self, client: Client) -> CollectionEpisode:
        """Fetch every show referenced by these episodes, and return them merged back in.

        A single request fetches all referenced shows (with their full additional
        information), then each episode's show is replaced by its enriched version.

        Args:
            client (Client): The BetaSeries API client to fetch shows with.

        Returns:
            CollectionEpisode: A new collection with each episode's show enriched.

        """
        shows = await client.fetch_shows(self.show_ids)
        episodes = tuple(
            dataclasses.replace(episode, show=shows.for_show(episode.show.id) or episode.show)
            for episode in self._episodes
        )
        return CollectionEpisode(episodes)
