"""A collection of shows, keyed by show id."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client
    from .show import Show


class CollectionShow:
    """Wrap a set of shows, keyed by show id.

    Attributes:
        _shows (dict[str, Show]): The wrapped shows, keyed by show id.

    """

    def __init__(self, shows: dict[str, Show]) -> None:
        """Initialize the collection.

        Args:
            shows (dict[str, Show]): The shows to wrap, keyed by show id.

        """
        self._shows = shows

    def for_show(self, show_id: str) -> Show | None:
        """Return the show for a single show id.

        Args:
            show_id (str): The BetaSeries show id.

        Returns:
            Show | None: The show, or None if not present in this collection.

        """
        return self._shows.get(show_id)

    async def fetch_episodes(self, client: Client) -> CollectionShow:
        """Fetch every show's episodes, and return them merged back in.

        Issues one request per show (Client.fetch_show_episodes() has no
        verified bulk support, unlike fetch_shows()).

        Args:
            client (Client): The BetaSeries API client to fetch episodes with.

        Returns:
            CollectionShow: A new collection with each show's episodes attached.

        """
        shows = {show_id: await show.fetch_episodes(client) for show_id, show in self._shows.items()}
        return CollectionShow(shows)

    async def fetch_additional_information(self, client: Client) -> CollectionShow:
        """Fetch every show's full details, and return the freshly-fetched shows.

        A single request fetches all shows in this collection (Client.fetch_shows()
        supports bulk ids); each show is entirely replaced by its freshly-fetched
        version (description/slug refreshed too, not just additional_information -
        see Show.fetch_additional_information()), except any unexpectedly absent
        from the response, which is kept as-is.

        Args:
            client (Client): The BetaSeries API client to fetch shows with.

        Returns:
            CollectionShow: A new collection with every show's full details populated.

        """
        fetched = await client.fetch_shows(self._shows.keys())
        shows = {show_id: fetched.for_show(show_id) or show for show_id, show in self._shows.items()}
        return CollectionShow(shows)
