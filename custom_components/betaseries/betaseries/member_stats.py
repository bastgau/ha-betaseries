"""Member statistics, as returned by GET /members/infos (member.stats)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemberStats:  # pylint: disable=too-many-instance-attributes
    """Represent the member's viewing statistics, as returned by GET /members/infos.

    Mostly mirrors the member.stats payload object, with one exception: xp is a
    member-level field in the raw API (a sibling of stats, not nested inside
    it), grouped in here instead since it is semantically a viewing statistic
    too.

    Several of these counters do not mean what their API name suggests. The
    descriptions below were verified against a real account by cross-checking
    each value with the categories betaseries.com itself displays, and by
    watching which counters moved when a single show was deleted.

    shows_to_watch counts shows never *started*, not shows with episodes left,
    and includes archived ones. It is unrelated to the show count
    GET /episodes/list reports, which answers a different question (shows with
    at least one unseen episode, archived excluded) and is normally larger.

    shows, shows_finished and shows_to_watch all include archived shows, so
    none of them matches the equivalent figure on the website, which counts
    only what it currently displays.

    member_since_days is a day count, not a date, and cannot be turned into one
    reliably: it does not increment at a fixed time, and repeated readings put
    the derived creation date on either side of the true one.

    Attributes:
        xp (int): Member experience points.
        episodes_to_watch (int): Number of unseen episodes, across every show.
        time_to_spend (int): Minutes left to watch everything pending.
        progress (float): Overall watch progress, in percent.
        shows_to_watch (int): Number of shows never started, archived ones included.
        movies_to_watch (int): Number of movies not yet watched.
        shows_current (int): Number of shows started and not yet finished.
        badges (int): Number of badges earned.
        shows (int): Total number of shows followed, archived ones included.
        shows_finished (int): Number of shows BetaSeries counts as finished, archived ones included.
        episodes (int): Total number of episodes watched.
        time_on_tv (int): Minutes spent watching episodes.
        movies (int): Total number of movies watched.
        streak_days (int): Current daily streak, in days.
        member_since_days (int): Number of days since account creation.
        episodes_per_month (float): Average number of episodes watched per month.
        favorite_genre (str): Most watched genre.

    """

    xp: int
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
