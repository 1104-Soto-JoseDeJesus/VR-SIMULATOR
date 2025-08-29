import heapq
from typing import Iterable, List, Set, Tuple
from math import hypot


class NavMesh:
    """A tiny grid based navigation mesh with A* path‑finding.

    The mesh stores walkable cells as integer ``(x, y)`` tuples.  It can be
    constructed either manually by supplying a set of cells or via
    :meth:`from_grid` which accepts an ASCII layout where ``#`` marks an
    obstacle and any other character is considered walkable.

    The :meth:`astar` method returns a list of waypoints (including ``start``
    and ``goal``) describing the shortest path computed using the A* search
    algorithm.  8‑directional movement is supported allowing diagonal travel
    for shorter, more natural paths.
    """

    def __init__(self, walkable: Iterable[Tuple[int, int]]):
        self.walkable: Set[Tuple[int, int]] = set(walkable)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_grid(cls, grid: List[str]) -> "NavMesh":
        """Create a mesh from an ASCII grid layout.

        ``grid`` is a list of strings representing the terrain layout.  Older
        versions of the project treated ``#`` characters as impassable
        obstacles.  Obstacle overlays have since been removed which means all
        cells are now considered walkable regardless of their character.
        """

        cells = set()
        for y, row in enumerate(grid):
            for x, _ in enumerate(row.strip("\n")):
                cells.add((x, y))
        return cls(cells)

    # ------------------------------------------------------------------
    # A* path finding
    # ------------------------------------------------------------------
    @staticmethod
    def _heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return hypot(a[0] - b[0], a[1] - b[1])

    def _neighbours(self, node: Tuple[int, int]):
        x, y = node
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nxt = (x + dx, y + dy)
                if nxt in self.walkable:
                    yield nxt

    def astar(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Return a list of waypoints from ``start`` to ``goal``.

        An empty list is returned when no path could be found.  Both ``start``
        and ``goal`` must be walkable cells.
        """

        start = tuple(start)
        goal = tuple(goal)
        if start not in self.walkable or goal not in self.walkable:
            raise ValueError("start or goal not on walkable mesh")

        frontier: List[Tuple[float, Tuple[int, int]]] = [(0.0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for nxt in self._neighbours(current):
                step_cost = hypot(nxt[0] - current[0], nxt[1] - current[1])
                new_cost = cost_so_far[current] + step_cost
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self._heuristic(goal, nxt)
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = current

        if goal not in came_from:
            return []

        path: List[Tuple[int, int]] = []
        cur = goal
        while cur is not None:
            path.append(cur)
            cur = came_from[cur]
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Path smoothing utilities
    # ------------------------------------------------------------------
    def line_of_sight(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """Return ``True`` if the straight line from ``a`` to ``b`` does not
        cross any non-walkable cells.

        A simple integer based Bresenham implementation is used so the check
        works for all 8 movement directions supported by :meth:`astar`.
        """

        x0, y0 = a
        x1, y1 = b
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        x, y = x0, y0
        n = 1 + max(dx, dy)
        x_inc = 1 if x1 > x0 else -1 if x1 < x0 else 0
        y_inc = 1 if y1 > y0 else -1 if y1 < y0 else 0
        error = dx - dy
        dx *= 2
        dy *= 2

        for _ in range(n):
            if (x, y) not in self.walkable:
                return False
            if x == x1 and y == y1:
                return True
            if error > 0:
                x += x_inc
                error -= dy
            elif error < 0:
                y += y_inc
                error += dx
            else:  # perfectly diagonal step
                x += x_inc
                y += y_inc
                error += dx - dy
        return True

    def simplify_path(self, path: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Collapse intermediate waypoints when a clear line of sight exists."""

        if not path:
            return []
        result = [path[0]]
        i = 0
        while i < len(path) - 1:
            j = i + 1
            while j < len(path) and self.line_of_sight(result[-1], path[j]):
                j += 1
            result.append(path[j - 1])
            i = j - 1
        return result
