"""Grid-based battlefield for multi-army movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Optional

from .navmesh import NavMesh

if TYPE_CHECKING:
    from .army_composition import Army


@dataclass
class Battlefield:
    """Simple 2D battlefield supporting NavMesh movement only."""

    width: int
    height: int
    navmesh: Optional[NavMesh] = None

    def within_bounds(self, x: float, y: float) -> bool:
        """Return True if the position is inside the battlefield."""
        return 0.0 <= x < self.width and 0.0 <= y < self.height

    def place_army(self, army: "Army", x: float, y: float) -> bool:
        """Place an army at a given location if within bounds."""
        if self.within_bounds(x, y):
            army.float_x = float(x)
            army.float_y = float(y)
            army.x = int(round(x))
            army.y = int(round(y))
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
            if self.within_bounds(army.float_x, army.float_y):
                marker = army.name[:1].upper()
                grid[int(army.float_y)][int(army.float_x)] = marker

        lines: List[str] = []
        for row in grid:
            lines.append(" ".join(row))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def render_with_coords(self, armies: List["Army"]) -> str:
        """Return a textual map listing each army's float coordinates."""

        lines: List[str] = []
        for army in armies:
            if army.current_troop_count <= 0:
                continue
            lines.append(f"{army.name}@{army.float_x:.1f},{army.float_y:.1f}")
        return "\n".join(lines)
