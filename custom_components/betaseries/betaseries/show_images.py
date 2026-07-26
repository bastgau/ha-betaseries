"""Public image URLs for a show, as returned by GET /shows/display."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShowImages:
    """Represent the public image URLs of a show (the "images" block of GET /shows/display).

    All URLs are hosted on pictures.betaseries.com and require no authentication
    to load (verified: no auth headers needed). Any field may be None if the
    show has no such image.

    Attributes:
        show (str | None): General show artwork.
        banner (str | None): Wide banner artwork.
        box (str | None): Box/cover artwork.
        poster (str | None): Portrait poster artwork.
        clearlogo (str | None): Transparent logo image.

    """

    show: str | None
    banner: str | None
    box: str | None
    poster: str | None
    clearlogo: str | None
