"""Member statistics, as returned by GET /members/infos (member.stats)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberStats:  # pylint: disable=too-many-instance-attributes
    """Represent the member.stats object returned by GET /members/infos.

    See CLAUDE.md §5 for the sensor spec these fields feed.

    Attributes:
        episodes_to_watch (int): Number of episodes available to watch.
        time_to_spend (int): Minutes left to watch everything pending.
        progress (float): Overall watch progress, in percent.
        shows_to_watch (int): Number of shows with unwatched episodes.
        movies_to_watch (int): Number of movies not yet watched.
        shows_current (int): Number of shows currently being followed.
        badges (int): Number of badges earned.
        shows (int): Total number of shows followed.
        shows_finished (int): Number of shows fully watched.
        episodes (int): Total number of episodes watched.
        time_on_tv (int): Minutes spent watching episodes.
        movies (int): Total number of movies watched.
        streak_days (int): Current daily streak, in days.
        member_since_days (int): Number of days since account creation.
        episodes_per_month (float): Average number of episodes watched per month.
        favorite_genre (str): Most watched genre.

    """

    episodes_to_watch: int
    time_to_spend: int
    progress: float
    shows_to_watch: int
    movies_to_watch: int
    shows_current: int
    badges: int
    shows: int
    shows_finished: int
    episodes: int
    time_on_tv: int
    movies: int
    streak_days: int
    member_since_days: int
    episodes_per_month: float
    favorite_genre: str
