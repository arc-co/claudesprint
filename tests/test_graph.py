"""Tests for graph utilities."""

import pytest

from claudesprint.utils.graph import detect_cycles


class TestDetectCycles:
    """Tests for detect_cycles function."""

    def test_empty_graph_returns_empty(self) -> None:
        """Empty graph should return no cycles."""
        result = detect_cycles(nodes=[], get_dependencies=lambda x: [])
        assert result == []

    def test_single_node_no_edges_returns_empty(self) -> None:
        """Single node with no dependencies should return no cycles."""
        result = detect_cycles(nodes=["a"], get_dependencies=lambda x: [])
        assert result == []

    def test_simple_cycle_detected(self) -> None:
        """Simple A->B->A cycle should be detected."""
        deps = {"a": ["b"], "b": ["a"]}
        result = detect_cycles(
            nodes=["a", "b"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 1
        # Cycle should be normalized to start from smallest
        assert result[0] == ["a", "b", "a"]

    def test_three_node_cycle_detected(self) -> None:
        """A->B->C->A cycle should be detected."""
        deps = {"a": ["b"], "b": ["c"], "c": ["a"]}
        result = detect_cycles(
            nodes=["a", "b", "c"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 1
        assert result[0] == ["a", "b", "c", "a"]

    def test_complex_dag_no_cycles(self) -> None:
        """Complex DAG with no cycles should return empty."""
        # Diamond pattern: a -> b, a -> c, b -> d, c -> d
        deps = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        result = detect_cycles(
            nodes=["a", "b", "c", "d"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert result == []

    def test_multiple_independent_cycles(self) -> None:
        """Multiple independent cycles should all be detected."""
        # Two separate cycles: a->b->a and c->d->c
        deps = {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"]}
        result = detect_cycles(
            nodes=["a", "b", "c", "d"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 2
        # Sort cycles for consistent comparison
        cycles_sorted = sorted(result, key=lambda c: c[0])
        assert cycles_sorted[0] == ["a", "b", "a"]
        assert cycles_sorted[1] == ["c", "d", "c"]

    def test_self_loop_detected(self) -> None:
        """Self-loop (A->A) should be detected."""
        deps = {"a": ["a"]}
        result = detect_cycles(
            nodes=["a"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 1
        assert result[0] == ["a", "a"]

    def test_cycle_with_external_node(self) -> None:
        """Cycle should be detected even when nodes have external edges."""
        # a -> b -> c -> b (cycle), d is separate
        deps = {"a": ["b"], "b": ["c"], "c": ["b"], "d": []}
        result = detect_cycles(
            nodes=["a", "b", "c", "d"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 1
        assert result[0] == ["b", "c", "b"]

    def test_dependency_to_nonexistent_node_ignored(self) -> None:
        """Dependencies to nodes not in the graph should be ignored."""
        deps = {"a": ["b", "nonexistent"], "b": ["a"]}
        result = detect_cycles(
            nodes=["a", "b"],  # "nonexistent" not in nodes
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert len(result) == 1
        assert result[0] == ["a", "b", "a"]

    def test_normalization_avoids_duplicates(self) -> None:
        """Cycles should be normalized to avoid duplicate detection."""
        # Both a->b->c->a and c->a->b->c are the same cycle
        deps = {"a": ["b"], "b": ["c"], "c": ["a"]}
        result = detect_cycles(
            nodes=["a", "b", "c"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        # Should only have one cycle, normalized
        assert len(result) == 1
        assert result[0] == ["a", "b", "c", "a"]

    def test_chain_no_cycle(self) -> None:
        """Linear chain should return no cycles."""
        deps = {"a": ["b"], "b": ["c"], "c": ["d"], "d": []}
        result = detect_cycles(
            nodes=["a", "b", "c", "d"],
            get_dependencies=lambda n: deps.get(n, []),
        )
        assert result == []
