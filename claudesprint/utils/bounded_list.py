"""Bounded list implementation to prevent unbounded array growth.

Provides a size-limited list that automatically prunes old entries
when capacity is reached, preventing memory issues.
"""

from collections import deque
from typing import Generic, Iterator, TypeVar, overload

T = TypeVar("T")

# Default size limits for various use cases
MAX_HISTORY_ENTRIES = 1000
MAX_LOG_ENTRIES = 5000
MAX_ITERATION_RECORDS = 500


class BoundedList(Generic[T]):
    """A list with a maximum size that prunes old entries on append.

    When the list is at capacity and a new item is appended, the oldest
    item is automatically removed (FIFO behavior).

    This is useful for:
    - History logs that shouldn't grow unbounded
    - Recent activity tracking
    - Circular buffers for debugging

    Example:
        history = BoundedList[str](max_size=100)
        for i in range(150):
            removed = history.append(f"entry-{i}")
            if removed:
                print(f"Pruned: {removed}")

        # history now contains entries 50-149
        assert len(history) == 100
        assert history[0] == "entry-50"
    """

    def __init__(
        self,
        max_size: int,
        items: list[T] | None = None,
    ) -> None:
        """Initialize BoundedList.

        Args:
            max_size: Maximum number of items to store.
            items: Optional initial items. If len(items) > max_size,
                only the last max_size items are kept.

        Raises:
            ValueError: If max_size < 1.
        """
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")

        self._max_size = max_size
        self._data: deque[T] = deque(maxlen=max_size)

        if items:
            # deque with maxlen automatically handles overflow
            self._data.extend(items)

    @property
    def max_size(self) -> int:
        """Maximum number of items this list can hold."""
        return self._max_size

    def append(self, item: T) -> T | None:
        """Append an item, returning any removed item if at capacity.

        Args:
            item: Item to append.

        Returns:
            The removed item if the list was at capacity, None otherwise.
        """
        removed: T | None = None

        if len(self._data) == self._max_size:
            removed = self._data[0]

        self._data.append(item)
        return removed

    def extend(self, items: list[T]) -> list[T]:
        """Extend with multiple items, returning any removed items.

        Args:
            items: Items to append.

        Returns:
            List of removed items (may be empty).
        """
        removed: list[T] = []

        for item in items:
            evicted = self.append(item)
            if evicted is not None:
                removed.append(evicted)

        return removed

    def clear(self) -> None:
        """Remove all items."""
        self._data.clear()

    def to_list(self) -> list[T]:
        """Return items as a standard list."""
        return list(self._data)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        """Get item(s) by index or slice."""
        if isinstance(index, slice):
            return list(self._data)[index]
        return self._data[index]

    def __setitem__(self, index: int, value: T) -> None:
        """Set item at index."""
        self._data[index] = value

    def __len__(self) -> int:
        """Return number of items."""
        return len(self._data)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items."""
        return iter(self._data)

    def __contains__(self, item: T) -> bool:
        """Check if item is in list."""
        return item in self._data

    def __bool__(self) -> bool:
        """Return True if list is non-empty."""
        return bool(self._data)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"BoundedList(max_size={self._max_size}, items={list(self._data)})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another BoundedList or list."""
        if isinstance(other, BoundedList):
            return (
                self._max_size == other._max_size
                and list(self._data) == list(other._data)
            )
        if isinstance(other, list):
            return list(self._data) == other
        return NotImplemented
