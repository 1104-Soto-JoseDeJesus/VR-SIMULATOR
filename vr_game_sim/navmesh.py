"""Simple navigation mesh with A* pathfinding and waypoint smoothing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import heapq
import math

Point = Tuple[float, float]


@dataclass
class Polygon:
    """Convex polygon within the NavMesh."""
    vertices: List[Point]
    neighbors: List[int]

    def centroid(self) -> Point:
        x = sum(v[0] for v in self.vertices) / len(self.vertices)
        y = sum(v[1] for v in self.vertices) / len(self.vertices)
        return (x, y)


def _point_in_poly(point: Point, verts: List[Point]) -> bool:
    """Return True if ``point`` lies inside the convex polygon ``verts``."""
    px, py = point
    sign = None
    for i in range(len(verts)):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % len(verts)]
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if cross == 0:
            continue
        curr = cross > 0
        if sign is None:
            sign = curr
        elif sign != curr:
            return False
    return True


class NavMesh:
    """Navigation mesh supporting pathfinding between arbitrary points."""

    def __init__(self, polygons: List[Polygon]):
        self.polygons = polygons

    # ------------------------------------------------------------------
    def _find_poly(self, point: Point) -> Optional[int]:
        for idx, poly in enumerate(self.polygons):
            if _point_in_poly(point, poly.vertices):
                return idx
        return None

    def _a_star(self, start: int, goal: int) -> List[int]:
        if start == goal:
            return [start]
        frontier: List[Tuple[float, int]] = []
        heapq.heappush(frontier, (0.0, start))
        came_from: Dict[int, Optional[int]] = {start: None}
        cost_so_far: Dict[int, float] = {start: 0.0}
        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for nxt in self.polygons[current].neighbors:
                new_cost = cost_so_far[current] + self._dist(current, nxt)
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self._dist(nxt, goal)
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = current
        if goal not in came_from:
            return []
        path = [goal]
        curr = goal
        while came_from[curr] is not None:
            curr = came_from[curr]
            path.append(curr)
        path.reverse()
        return path

    def _dist(self, a_idx: int, b_idx: int) -> float:
        a = self.polygons[a_idx].centroid()
        b = self.polygons[b_idx].centroid()
        return math.hypot(a[0] - b[0], a[1] - b[1])

    # ------------------------------------------------------------------
    def find_path(self, start: Point, goal: Point) -> List[Point]:
        """Return a list of waypoints from ``start`` to ``goal``."""
        s_poly = self._find_poly(start)
        g_poly = self._find_poly(goal)
        if s_poly is None or g_poly is None:
            return [goal]
        poly_path = self._a_star(s_poly, g_poly)
        if not poly_path:
            return [goal]
        pts: List[Point] = [start]
        for idx in poly_path[1:]:
            pts.append(self.polygons[idx].centroid())
        pts.append(goal)
        return _funnel(pts)


def _funnel(points: List[Point]) -> List[Point]:
    """Very small colinear-point remover acting as a simple funnel."""
    if len(points) <= 2:
        return points
    result: List[Point] = [points[0]]
    for i in range(1, len(points) - 1):
        a = result[-1]
        b = points[i]
        c = points[i + 1]
        if _colinear(a, b, c):
            continue
        result.append(b)
    result.append(points[-1])
    return result


def _colinear(a: Point, b: Point, c: Point, eps: float = 1e-6) -> bool:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < eps
