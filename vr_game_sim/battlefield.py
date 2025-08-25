"""Grid-based battlefield for multi-army movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING, Dict

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


def step_towards(battlefield: "Battlefield", a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    """Return the next coordinate on the shortest path from ``a`` to ``b``.

    A simple breadth-first search is used so movement no longer favours
    horizontal steps before vertical ones.  If ``b`` cannot be reached within
    the battlefield bounds the original coordinate ``a`` is returned.
    """
    if a == b:
        return a

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

    def within_bounds(self, x: int, y: int) -> bool:
        """Return True if the position is inside the battlefield."""
        return 0 <= x < self.width and 0 <= y < self.height

    def place_army(self, army: "Army", x: int, y: int) -> bool:
        """Place an army at a given location if within bounds."""
        if self.within_bounds(x, y):
            army.x = x
            army.y = y
            return True
        return False

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
