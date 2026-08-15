"""Additional show details, as returned by GET /shows/display (beyond the light Show)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .show_images import ShowImages


@dataclass(frozen=True)
class ShowAdditionalInformation:  # pylint: disable=too-many-instance-attributes
    """Represent the richer show details only available via GET /shows/display.

    Kept as its own type rather than merged flat into Show, since an Episode's
    embedded Show never has this populated - only Client.fetch_shows() does.

    Attributes:
        original_title (str): Original-language title.
        imdb_id (str | None): IMDB id, if known.
        themoviedb_id (str | None): TheMovieDB id, if known.
        genres (tuple[str, ...]): Genres (localized).
        showrunners (tuple[str, ...]): Showrunner names.
        aliases (tuple[str, ...]): Alternate/localized titles.
        seasons (int): Number of seasons.
        followers (int): Number of BetaSeries members following this show.
        network (str): Broadcasting network.
        country (str | None): Country of origin.
        original_language (str | None): Original language, localized (e.g. "allemand").
        length (int): Average episode length, in minutes.
        rating (str): Content rating.
        notes_mean (float): Average member rating.
        notes_total (int): Number of member ratings.
        trailer_url (str | None): Playable URL of the latest trailer, None if there is none or its host is not one this client can build a URL for.
        resource_url (str): Link to the show's BetaSeries page.
        images (ShowImages): The show's images.
        creation (str | None): Year the show was created ("2024"), None if the payload has none.
        broadcast_status (str | None): Broadcast state ("Continuing"/"Ended"), None if the payload has none. Named apart from `rating` (a content rating) to keep the two "status-looking" fields distinguishable.
        platforms (tuple[str, ...]): Names of the SVOD platforms streaming this show.
        in_account (bool): Whether this show is in the authenticated member's account.

    """

    original_title: str
    imdb_id: str | None
    themoviedb_id: str | None
    genres: tuple[str, ...]
    showrunners: tuple[str, ...]
    aliases: tuple[str, ...]
    seasons: int
    followers: int
    network: str
    country: str | None
    original_language: str | None
    length: int
    rating: str
    notes_mean: float
    notes_total: int
    trailer_url: str | None
    resource_url: str
    images: ShowImages
    creation: str | None = None
    broadcast_status: str | None = None
    platforms: tuple[str, ...] = ()
    in_account: bool = False
