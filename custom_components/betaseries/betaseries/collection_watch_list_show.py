"""A collection of the member's shows still to watch, as returned by GET /episodes/list."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .watch_list_show import WatchListShow


class CollectionWatchListShow:
    """Wrap the member's shows still to watch.

    Holds only the shows the endpoint returned, which the showsLimit/limit
    query params cap - the endpoint's own global counters are kept apart
    (see Client.fetch_watch_list), since they describe the whole watch list
    rather than these shows.

    Attributes:
        _shows (tuple[WatchListShow, ...]): The wrapped shows.

    """

    def __init__(self, shows: tuple[WatchListShow, ...]) -> None:
        """Initialize the collection.

        Args:
            shows (tuple[WatchListShow, ...]): The shows to wrap, in API order.

        """
        self._shows = shows

    def __iter__(self) -> Iterator[WatchListShow]:
        """Iterate over the wrapped shows.

        Returns:
            Iterator[WatchListShow]: An iterator over the shows.

        """
        return iter(self._shows)

    def __len__(self) -> int:
        """Return the number of wrapped shows.

        Returns:
            int: The number of shows.

        """
        return len(self._shows)

    @property
    def show_ids(self) -> frozenset[str]:
        """Return the unique show ids of the wrapped shows.

        Returns:
            frozenset[str]: The shows' ids.

        """
        return frozenset(show.id for show in self._shows)
