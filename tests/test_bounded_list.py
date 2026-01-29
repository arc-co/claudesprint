"""Tests for the BoundedList utility."""

import pytest

from claudesprint.utils.bounded_list import (
    BoundedList,
    MAX_HISTORY_ENTRIES,
    MAX_LOG_ENTRIES,
    MAX_ITERATION_RECORDS,
)


class TestBoundedListCreation:
    """Tests for BoundedList initialization."""

    def test_create_empty(self):
        """Create empty bounded list."""
        bl = BoundedList[int](max_size=10)
        assert len(bl) == 0
        assert bl.max_size == 10

    def test_create_with_items(self):
        """Create with initial items."""
        bl = BoundedList[int](max_size=10, items=[1, 2, 3])
        assert len(bl) == 3
        assert bl.to_list() == [1, 2, 3]

    def test_create_with_overflow_items(self):
        """Items exceeding max_size are pruned from the front."""
        bl = BoundedList[int](max_size=3, items=[1, 2, 3, 4, 5])
        assert len(bl) == 3
        assert bl.to_list() == [3, 4, 5]

    def test_invalid_max_size(self):
        """max_size must be >= 1."""
        with pytest.raises(ValueError):
            BoundedList[int](max_size=0)

        with pytest.raises(ValueError):
            BoundedList[int](max_size=-1)


class TestBoundedListAppend:
    """Tests for append behavior."""

    def test_append_under_capacity(self):
        """Append returns None when under capacity."""
        bl = BoundedList[int](max_size=5)
        removed = bl.append(1)
        assert removed is None
        assert len(bl) == 1

    def test_append_at_capacity(self):
        """Append returns removed item when at capacity."""
        bl = BoundedList[int](max_size=3, items=[1, 2, 3])
        removed = bl.append(4)
        assert removed == 1
        assert bl.to_list() == [2, 3, 4]

    def test_append_fifo_order(self):
        """Items are removed in FIFO order."""
        bl = BoundedList[int](max_size=3)
        for i in range(1, 7):
            bl.append(i)

        # Should have last 3 items
        assert bl.to_list() == [4, 5, 6]

    def test_append_prunes_on_append_not_after(self):
        """Pruning happens during append, not after."""
        bl = BoundedList[int](max_size=2, items=[1, 2])

        # At this point, list is full
        assert len(bl) == 2

        # Append should return removed item immediately
        removed = bl.append(3)
        assert removed == 1
        assert len(bl) == 2  # Still at max size


class TestBoundedListExtend:
    """Tests for extend behavior."""

    def test_extend_under_capacity(self):
        """Extend returns empty list when under capacity."""
        bl = BoundedList[int](max_size=10)
        removed = bl.extend([1, 2, 3])
        assert removed == []
        assert len(bl) == 3

    def test_extend_with_overflow(self):
        """Extend returns all removed items."""
        bl = BoundedList[int](max_size=3, items=[1, 2, 3])
        removed = bl.extend([4, 5])
        assert removed == [1, 2]
        assert bl.to_list() == [3, 4, 5]

    def test_extend_empty_list(self):
        """Extending with empty list does nothing."""
        bl = BoundedList[int](max_size=3, items=[1, 2])
        removed = bl.extend([])
        assert removed == []
        assert len(bl) == 2


class TestBoundedListAccess:
    """Tests for list access operations."""

    def test_getitem_by_index(self):
        """Access items by index."""
        bl = BoundedList[str](max_size=5, items=["a", "b", "c"])
        assert bl[0] == "a"
        assert bl[1] == "b"
        assert bl[-1] == "c"

    def test_getitem_by_slice(self):
        """Access items by slice."""
        bl = BoundedList[int](max_size=10, items=[1, 2, 3, 4, 5])
        assert bl[1:4] == [2, 3, 4]
        assert bl[::2] == [1, 3, 5]

    def test_setitem(self):
        """Set items by index."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl[1] = 20
        assert bl.to_list() == [1, 20, 3]

    def test_contains(self):
        """Check item membership."""
        bl = BoundedList[str](max_size=5, items=["a", "b", "c"])
        assert "a" in bl
        assert "d" not in bl

    def test_iteration(self):
        """Iterate over items."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        result = [x * 2 for x in bl]
        assert result == [2, 4, 6]


class TestBoundedListClear:
    """Tests for clear operation."""

    def test_clear_removes_all_items(self):
        """Clear removes all items."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl.clear()
        assert len(bl) == 0
        assert bl.to_list() == []

    def test_clear_preserves_max_size(self):
        """Clear preserves max_size."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl.clear()
        assert bl.max_size == 5


class TestBoundedListEquality:
    """Tests for equality comparison."""

    def test_equal_bounded_lists(self):
        """Equal bounded lists compare equal."""
        bl1 = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl2 = BoundedList[int](max_size=5, items=[1, 2, 3])
        assert bl1 == bl2

    def test_different_items_not_equal(self):
        """Different items are not equal."""
        bl1 = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl2 = BoundedList[int](max_size=5, items=[1, 2, 4])
        assert bl1 != bl2

    def test_different_max_size_not_equal(self):
        """Different max_size are not equal."""
        bl1 = BoundedList[int](max_size=5, items=[1, 2, 3])
        bl2 = BoundedList[int](max_size=10, items=[1, 2, 3])
        assert bl1 != bl2

    def test_equal_to_list(self):
        """BoundedList can equal a regular list (items only)."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        assert bl == [1, 2, 3]

    def test_not_equal_to_other_types(self):
        """BoundedList not equal to incompatible types."""
        bl = BoundedList[int](max_size=5, items=[1, 2, 3])
        assert bl != "not a list"
        assert bl != 123


class TestBoundedListBool:
    """Tests for boolean conversion."""

    def test_empty_is_falsy(self):
        """Empty list is falsy."""
        bl = BoundedList[int](max_size=5)
        assert not bl
        assert bool(bl) is False

    def test_non_empty_is_truthy(self):
        """Non-empty list is truthy."""
        bl = BoundedList[int](max_size=5, items=[1])
        assert bl
        assert bool(bl) is True


class TestBoundedListRepr:
    """Tests for string representation."""

    def test_repr_includes_info(self):
        """Repr includes max_size and items."""
        bl = BoundedList[int](max_size=5, items=[1, 2])
        repr_str = repr(bl)
        assert "BoundedList" in repr_str
        assert "max_size=5" in repr_str
        assert "[1, 2]" in repr_str


class TestConstants:
    """Tests for default size constants."""

    def test_constants_defined(self):
        """Default constants are defined."""
        assert MAX_HISTORY_ENTRIES == 1000
        assert MAX_LOG_ENTRIES == 5000
        assert MAX_ITERATION_RECORDS == 500

    def test_use_with_constants(self):
        """Constants work with BoundedList."""
        history = BoundedList[str](max_size=MAX_HISTORY_ENTRIES)
        assert history.max_size == 1000
