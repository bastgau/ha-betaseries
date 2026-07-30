"""A collection of the member's earned badges, as returned by GET /members/badges."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .badge import Badge


class CollectionBadge:
    """Wrap the member's earned badges.

    Attributes:
        _badges (tuple[Badge, ...]): The wrapped badges.

    """

    def __init__(self, badges: tuple[Badge, ...]) -> None:
        """Initialize the collection.

        Args:
            badges (tuple[Badge, ...]): The badges to wrap.

        """
        self._badges = badges

    def __iter__(self) -> Iterator[Badge]:
        """Iterate over the wrapped badges.

        Returns:
            Iterator[Badge]: An iterator over the badges.

        """
        return iter(self._badges)

    def __len__(self) -> int:
        """Return the number of wrapped badges.

        Returns:
            int: The number of badges.

        """
        return len(self._badges)
