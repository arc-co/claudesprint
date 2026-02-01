"""Graph utilities for dependency analysis."""

from collections.abc import Callable


def detect_cycles(
    nodes: list[str],
    get_dependencies: Callable[[str], list[str]],
) -> list[list[str]]:
    """Detect circular dependencies in a directed graph.

    Uses DFS to find all cycles in the graph. Cycles are normalized to start
    from the smallest ID to avoid duplicate detection.

    Args:
        nodes: List of node IDs in the graph
        get_dependencies: Function that takes a node ID and returns its dependencies

    Returns:
        List of cycles, where each cycle is a list of node IDs ending with
        the starting node (e.g., ["a", "b", "c", "a"]). Empty list if no cycles.

    Example:
        >>> nodes = ["a", "b", "c"]
        >>> deps = {"a": ["b"], "b": ["c"], "c": ["a"]}
        >>> detect_cycles(nodes, lambda n: deps.get(n, []))
        [['a', 'b', 'c', 'a']]
    """
    node_set = set(nodes)
    cycles: list[list[str]] = []

    def find_cycle_from(start_id: str, path: list[str], visited: set[str]) -> None:
        """DFS to find cycles starting from a node."""
        if start_id in path:
            # Found a cycle - extract it
            cycle_start = path.index(start_id)
            cycle = path[cycle_start:] + [start_id]
            # Normalize cycle (start from smallest ID) to avoid duplicates
            min_idx = cycle.index(min(cycle[:-1]))  # Exclude last (duplicate of first)
            normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
            if normalized not in cycles:
                cycles.append(normalized)
            return

        if start_id in visited:
            return

        visited.add(start_id)
        if start_id not in node_set:
            return

        for dep_id in get_dependencies(start_id):
            if dep_id in node_set:
                find_cycle_from(dep_id, path + [start_id], visited)

    # Check from each node
    for node in nodes:
        find_cycle_from(node, [], set())

    return cycles
