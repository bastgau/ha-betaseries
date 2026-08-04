"""A single show of the member's watch list, as returned by GET /episodes/list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .collection_episode import CollectionEpisode


@dataclass(frozen=True)
class WatchListShow:
    """Represent one show of the watch list, with the episodes left to watch.

    Attributes:
        id (str): BetaSeries show id.
        title (str): Show title.
        remaining (int): Episodes left to watch for this show, regardless of how many are listed below.
        poster (str | None): Poster URL carried by the payload itself, if any.
        episodes (CollectionEpisode): The unseen episodes, capped by the requested per-show limit.

    """

    id: str
    title: str
    remaining: int
    poster: str | None
    episodes: CollectionEpisode
