"""Grid-based battlefield for multi-army movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

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


def step_towards(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    """Return the neighbour of ``a`` that is closest to ``b``."""
    best = a
    best_dist = hex_distance(a, b)
    for dq, dr in HEX_DIRECTIONS:
        candidate = (a[0] + dq, a[1] + dr)
        dist = hex_distance(candidate, b)
        if dist < best_dist:
            best = candidate
            best_dist = dist
    return best


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
