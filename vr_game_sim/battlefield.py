"""Grid-based battlefield for multi-army movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .army_composition import Army


@dataclass
class Battlefield:
    width: int
    height: int

    def within_bounds(self, x: int, y: int) -> bool:
        """Return True if the position is inside the battlefield."""
        return 0 <= x < self.width and 0 <= y < self.height

    def place_army(self, army: Army, x: int, y: int) -> bool:
        """Place an army at a given location if within bounds."""
        if self.within_bounds(x, y):
            army.x = x
            army.y = y
            return True
        return False

    def render(self, armies: List[Army]) -> str:
        """Return a simple string representation of the battlefield."""
        grid = [["." for _ in range(self.width)] for _ in range(self.height)]
        for army in armies:
            if army.current_troop_count <= 0:
                continue
            if self.within_bounds(army.x, army.y):
                marker = army.name[:1].upper()
                grid[army.y][army.x] = marker
        return "\n".join(" ".join(row) for row in grid)
