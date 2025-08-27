import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_in_polygon(point: Point, polygon: List[Point]) -> bool:
    """Return True if point is inside polygon using ray casting."""
    x, y = point
    inside = False
    n = len(polygon)
    px1, py1 = polygon[0]
    for i in range(n + 1):
        px2, py2 = polygon[i % n]
        if min(py1, py2) < y <= max(py1, py2) and x <= max(px1, px2):
            if py1 != py2:
                xinters = (y - py1) * (px2 - px1) / (py2 - py1) + px1
            if px1 == px2 or x <= xinters:
                inside = not inside
        px1, py1 = px2, py2
    return inside


@dataclass
class Polygon:
    id: int
    vertices: List[Point]
    neighbors: List[int]

    def centroid(self) -> Point:
        x = sum(p[0] for p in self.vertices) / len(self.vertices)
        y = sum(p[1] for p in self.vertices) / len(self.vertices)
        return (x, y)


class NavMesh:
    """Simple navmesh of connected polygons with A* path finding."""

    def __init__(self, polygons: Dict[int, Polygon]):
        self.polygons = polygons

    @classmethod
    def from_json(cls, path: str | Path) -> "NavMesh":
        data = json.loads(Path(path).read_text())
        polygons = {
            p["id"]: Polygon(
                id=p["id"],
                vertices=[tuple(v) for v in p["vertices"]],
                neighbors=p.get("neighbors", []),
            )
            for p in data["polygons"]
        }
        return cls(polygons)

    def find_polygon(self, point: Point) -> Optional[Polygon]:
        for poly in self.polygons.values():
            if _point_in_polygon(point, poly.vertices):
                return poly
        return None

    def find_path(self, start: Point, goal: Point) -> List[Point]:
        start_poly = self.find_polygon(start)
        goal_poly = self.find_polygon(goal)
        if start_poly is None or goal_poly is None:
            return []

        import heapq

        open_set: List[Tuple[float, int]] = []
        heapq.heappush(open_set, (0.0, start_poly.id))
        came_from: Dict[int, Optional[int]] = {start_poly.id: None}
        g_score: Dict[int, float] = {start_poly.id: 0.0}

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal_poly.id:
                break
            current_poly = self.polygons[current]
            for neighbor_id in current_poly.neighbors:
                neighbor_poly = self.polygons[neighbor_id]
                tentative_g = g_score[current] + _distance(
                    current_poly.centroid(), neighbor_poly.centroid()
                )
                if tentative_g < g_score.get(neighbor_id, float("inf")):
                    came_from[neighbor_id] = current
                    g_score[neighbor_id] = tentative_g
                    f_score = tentative_g + _distance(
                        neighbor_poly.centroid(), goal_poly.centroid()
                    )
                    heapq.heappush(open_set, (f_score, neighbor_id))

        if goal_poly.id not in came_from:
            return []

        # Reconstruct polygon path
        poly_path: List[int] = []
        cur = goal_poly.id
        while cur is not None:
            poly_path.append(cur)
            cur = came_from.get(cur)
        poly_path.reverse()

        path: List[Point] = [start]
        for pid in poly_path[1:-1]:
            path.append(self.polygons[pid].centroid())
        path.append(goal)
        return path


__all__ = ["NavMesh", "Polygon"]
