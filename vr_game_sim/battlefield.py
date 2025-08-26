"""Grid-based battlefield for multi-army movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING, Dict, Optional

from .navmesh import NavMesh

if TYPE_CHECKING:
    from .army_composition import Army

# Hex-grid helpers ------------------------------------------------------------
HEX_DIRECTIONS: List[Tuple[int, int]] = [
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
]


def hex_distance(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Return the hex distance between ``a`` and ``b``."""
    dq = b[0] - a[0]
    dr = b[1] - a[1]
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


def _axial_to_cube(q: int, r: int) -> Tuple[float, float, float]:
    return (q, -q - r, r)


def _cube_to_axial(x: float, y: float, z: float) -> Tuple[int, int]:
    return (int(round(x)), int(round(z)))


def _cube_lerp(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _cube_round(cube: Tuple[float, float, float]) -> Tuple[float, float, float]:
    rx, ry, rz = round(cube[0]), round(cube[1]), round(cube[2])
    x_diff = abs(rx - cube[0])
    y_diff = abs(ry - cube[1])
    z_diff = abs(rz - cube[2])
    if x_diff > y_diff and x_diff > z_diff:
        rx = -ry - rz
    elif y_diff > z_diff:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return (rx, ry, rz)


def _straight_line_step(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    """Return the next hex along the straight line from ``a`` to ``b``."""
    n = hex_distance(a, b)
    if n == 0:
        return a
    ac = _axial_to_cube(*a)
    bc = _axial_to_cube(*b)
    step = _cube_lerp(ac, bc, 1.0 / n)
    return _cube_to_axial(*_cube_round(step))


def step_towards(battlefield: "Battlefield", a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    """Return the next coordinate on the path from ``a`` to ``b``.

    A straight-line hex interpolation is attempted first so armies follow the
    most direct route.  If that step would fall outside the battlefield bounds
    a breadth-first search is used as a fallback to keep movement within the
    map.
    """
    if a == b:
        return a

    step = _straight_line_step(a, b)
    if battlefield.within_bounds(*step):
        return step

    frontier: List[Tuple[int, int]] = [a]
    came_from: Dict[Tuple[int, int], Tuple[int, int] | None] = {a: None}
    while frontier:
        current = frontier.pop(0)
        if current == b:
            break
        for dq, dr in HEX_DIRECTIONS:
            nxt = (current[0] + dq, current[1] + dr)
            if not battlefield.within_bounds(*nxt):
                continue
            if nxt not in came_from:
                frontier.append(nxt)
                came_from[nxt] = current
    if b not in came_from:
        return a
    curr = b
    while came_from[curr] and came_from[curr] != a:
        curr = came_from[curr]
    return curr


@dataclass
class Battlefield:
    width: int
    height: int
    navmesh: Optional[NavMesh] = None

    def within_bounds(self, x: int, y: int) -> bool:
        """Return True if the position is inside the battlefield."""
        return 0 <= x < self.width and 0 <= y < self.height

    def place_army(self, army: "Army", x: int, y: int) -> bool:
        """Place an army at a given location if within bounds."""
        if self.within_bounds(x, y):
            army.x = x
            army.y = y
            army.float_x = float(x)
            army.float_y = float(y)
            return True
        return False

    def load_navmesh(self, navmesh: NavMesh) -> None:
        """Attach a navigation mesh to the battlefield."""
        self.navmesh = navmesh

    def render(self, armies: List["Army"]) -> str:
        """Return a simple string representation of the battlefield."""
        grid = [["." for _ in range(self.width)] for _ in range(self.height)]
        for army in armies:
            if army.current_troop_count <= 0:
                continue
            if self.within_bounds(army.x, army.y):
                marker = army.name[:1].upper()
                grid[army.y][army.x] = marker

        lines: List[str] = []
        for y, row in enumerate(grid):
            prefix = " " if y % 2 == 1 else ""
            lines.append(prefix + " ".join(row))
        return "\n".join(lines)
