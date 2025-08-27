from __future__ import annotations

import math
import heapq
from collections import defaultdict
from typing import Dict, List, Tuple, Iterable, Optional


class NavMesh:
    """Simple navigation mesh backed by a graph.

    Nodes are identified by arbitrary hashable ids and store 2-D coordinates.
    Edges are bidirectional with an implied Euclidean cost.
    The mesh exposes a minimal A* implementation used by the
    :class:`MovementController` to plan paths.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, Tuple[float, float]] = {}
        self._edges: Dict[str, List[str]] = defaultdict(list)

    # -- graph construction -------------------------------------------------
    def add_node(self, node_id: str, position: Tuple[float, float]) -> None:
        self._nodes[node_id] = position

    def add_edge(self, a: str, b: str) -> None:
        self._edges[a].append(b)
        self._edges[b].append(a)

    # -- helpers ------------------------------------------------------------
    def _heuristic(self, a: str, b: str) -> float:
        ax, ay = self._nodes[a]
        bx, by = self._nodes[b]
        return math.hypot(ax - bx, ay - by)

    def _nearest_node(self, position: Tuple[float, float]) -> str:
        """Return id of the node closest to ``position``."""
        return min(self._nodes, key=lambda nid: math.hypot(self._nodes[nid][0] - position[0],
                                                          self._nodes[nid][1] - position[1]))

    # -- path finding -------------------------------------------------------
    def find_path(self, start: Tuple[float, float], goal: Tuple[float, float]) -> List[Tuple[float, float]]:
        """Compute a path from ``start`` to ``goal`` using A*.

        ``start`` and ``goal`` are arbitrary positions; they are temporarily
        linked to the nearest nodes in the mesh.  The returned list always
        starts with ``start`` and ends with ``goal``.
        """
        start_id = "__start__"
        goal_id = "__goal__"

        nearest_start = self._nearest_node(start)
        nearest_goal = self._nearest_node(goal)

        # Temporarily insert the start/goal into the graph.
        self._nodes[start_id] = start
        self._nodes[goal_id] = goal
        self._edges[start_id] = [nearest_start]
        self._edges[nearest_start].append(start_id)
        self._edges[goal_id] = [nearest_goal]
        self._edges[nearest_goal].append(goal_id)

        def a_star() -> List[str]:
            open_set: List[Tuple[float, str]] = []
            heapq.heappush(open_set, (0.0, start_id))
            came_from: Dict[str, Optional[str]] = {start_id: None}
            g_score: Dict[str, float] = defaultdict(lambda: float("inf"))
            g_score[start_id] = 0.0

            while open_set:
                _, current = heapq.heappop(open_set)
                if current == goal_id:
                    # Reconstruct path
                    path: List[str] = [current]
                    while came_from[current] is not None:
                        current = came_from[current]  # type: ignore[assignment]
                        path.append(current)
                    path.reverse()
                    return path

                for neighbour in self._edges[current]:
                    tentative = g_score[current] + self._heuristic(current, neighbour)
                    if tentative < g_score[neighbour]:
                        came_from[neighbour] = current
                        g_score[neighbour] = tentative
                        f_score = tentative + self._heuristic(neighbour, goal_id)
                        heapq.heappush(open_set, (f_score, neighbour))

            return []

        path_ids = a_star()

        # Cleanup temporary nodes/edges.
        self._edges[nearest_start].remove(start_id)
        self._edges[nearest_goal].remove(goal_id)
        del self._edges[start_id]
        del self._edges[goal_id]
        del self._nodes[start_id]
        del self._nodes[goal_id]

        return [start] + [self._nodes[nid] for nid in path_ids[1:-1]] + [goal]


class MovementController:
    """Handles unit movement across the battlefield at a fixed tick rate.

    The controller keeps track of per-army positions and active paths.  Each
    call to :meth:`tick` advances all armies by ``speed / tick_rate`` units
    along their paths.  Paths are generated using a :class:`NavMesh`.

    The controller is intentionally stateless w.r.t. physics; it only performs
    linear interpolation between successive waypoints.
    """

    def __init__(self, navmesh: NavMesh, tick_rate: int = 1000) -> None:
        self.navmesh = navmesh
        self.tick_rate = tick_rate
        self._positions: Dict[str, Tuple[float, float]] = {}
        self._speeds: Dict[str, float] = {}
        self._paths: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    # -- registration -------------------------------------------------------
    def register_army(self, army_name: str, position: Tuple[float, float], speed: float) -> None:
        """Register a new army with ``position`` and movement ``speed``."""
        self._positions[army_name] = position
        self._speeds[army_name] = speed
        self._paths[army_name] = []

    # -- waypoint management ------------------------------------------------
    def set_waypoint(self, army_name: str, destination: Tuple[float, float]) -> None:
        """Set a movement destination using drag-and-drop semantics."""
        start = self._positions[army_name]
        path = self.navmesh.find_path(start, destination)
        # The first element equals the current position; discard it.
        self._paths[army_name] = path[1:]

    def snap_to_target(self, army_name: str, target: Tuple[float, float], attack_range: float) -> None:
        """Move towards ``target`` but stop ``attack_range`` units away."""
        start = self._positions[army_name]
        path = self.navmesh.find_path(start, target)
        if len(path) < 2:
            self._paths[army_name] = []
            return
        prefix = path[:-1]
        last = path[-1]
        prev = prefix[-1] if prefix else start
        dx, dy = last[0] - prev[0], last[1] - prev[1]
        seg_len = math.hypot(dx, dy)
        if seg_len > attack_range:
            ratio = (seg_len - attack_range) / seg_len
            new_last = (prev[0] + dx * ratio, prev[1] + dy * ratio)
            path = prefix + [new_last]
        else:
            path = prefix
        self._paths[army_name] = path[1:]

    # -- ticking ------------------------------------------------------------
    def tick(self) -> None:
        """Advance all registered armies by one tick."""
        for army, path in self._paths.items():
            if not path:
                continue
            pos = self._positions[army]
            distance_remaining = self._speeds[army] / self.tick_rate
            while path and distance_remaining > 0:
                waypoint = path[0]
                dx = waypoint[0] - pos[0]
                dy = waypoint[1] - pos[1]
                segment = math.hypot(dx, dy)
                if distance_remaining >= segment:
                    pos = waypoint
                    path.pop(0)
                    distance_remaining -= segment
                else:
                    ratio = distance_remaining / segment
                    pos = (pos[0] + dx * ratio, pos[1] + dy * ratio)
                    distance_remaining = 0
            self._positions[army] = pos

    # -- queries ------------------------------------------------------------
    def get_position(self, army_name: str) -> Tuple[float, float]:
        return self._positions[army_name]
