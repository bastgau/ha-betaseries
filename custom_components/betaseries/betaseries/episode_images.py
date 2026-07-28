"""Public image URLs for an episode, derived from its id."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpisodeImages:
    """Represent the public image URL(s) of an episode.

    Unlike ShowImages (fetched verbatim from GET /shows/display), this is
    entirely derived from the episode's id via GET /pictures/episodes -
    verified public and loadable without authentication (see CLAUDE.md §4:
    a valid id redirects to a pictures.betaseries.com image; an invalid id
    without auth returns a JSON error instead of falling back to a default
    image, unlike an authenticated call).

    Attributes:
        episode (str): The episode's picture URL.

    """

    episode: str
