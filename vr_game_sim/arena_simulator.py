from __future__ import annotations
from typing import Dict, Tuple, List, Optional

from .army_composition import Army
from .game_simulator import GameSimulator


class ArenaSimulator:
    """Arena battles on a 2x4 grid for *each* side.

    Both attackers and defenders can field armies on their own two column by
    four row grid.  Columns represent the front and back ranks while rows are
    lanes from top to bottom.  Engagement order iterates lanes from front to
    back and prioritises the front column within each lane.

    Target selection favours enemies in the same lane as the attacker.  If the
    lane is empty, columns are inspected by proximity starting with the
    attacker's column and scanning lanes from the front towards the back.
    """

    GRID_COLS = 2
    GRID_ROWS = 4

    def __init__(self, armies_side1: List[Army], armies_side2: List[Army]):
        # Store armies keyed by their (col, row) position
        self.armies_side1: Dict[Tuple[int, int], Army] = {
            army.position: army for army in armies_side1 if army.position is not None
        }
        self.armies_side2: Dict[Tuple[int, int], Army] = {
            army.position: army for army in armies_side2 if army.position is not None
        }
        self.round: int = 0
        self.winner: Optional[int] = None

        # Internal index for cycling through grid positions in the desired
        # attacker order (front lanes first).
        self._order_index: int = 0

    def _position_order(self) -> List[Tuple[int, int]]:
        """Return attacker positions in row-major order, front column first."""
        order: List[Tuple[int, int]] = []
        for row in range(self.GRID_ROWS):
            for col in range(self.GRID_COLS):
                order.append((col, row))
        return order

    def _next_attacker_pos(self) -> Optional[Tuple[int, int]]:
        """Return the next position from side1 that should initiate a battle."""
        order = self._position_order()
        searched = 0
        while searched < len(order):
            pos = order[self._order_index]
            self._order_index = (self._order_index + 1) % len(order)
            if pos in self.armies_side1:
                return pos
            searched += 1
        return None

    def _select_target(
        self, pos: Tuple[int, int], enemies: Dict[Tuple[int, int], Army]
    ) -> Optional[Tuple[int, int]]:
        """Return the target position following arena targeting priorities.

        Enemies in the same lane (row) are preferred, inspecting columns by
        proximity to the attacker.  If the lane holds no enemies the remaining
        columns are checked, scanning rows from the front towards the back.
        """
        col, row = pos
        column_order = sorted(range(self.GRID_COLS), key=lambda c: abs(c - col))

        # First inspect enemies within the same row starting with the nearest column
        for c in column_order:
            candidate = (c, row)
            if candidate in enemies:
                return candidate

        # No enemy in the same row, search other rows
        for c in column_order:
            for r in range(self.GRID_ROWS):  # front to back
                if r == row:
                    continue
                candidate = (c, r)
                if candidate in enemies:
                    return candidate
        return None

    def simulate_battle(self) -> Dict[str, Dict[Tuple[int, int], float]]:
        """Run sequential battles until one side runs out of armies.

        Each fight is resolved using ``GameSimulator``. The winning army keeps its
        remaining troops and may fight again if opponents remain. The function
        returns a mapping of surviving troops per position for both sides.
        """
        # Ensure armies start fresh
        for army in list(self.armies_side1.values()) + list(self.armies_side2.values()):
            army.reset_for_new_battle()

        while self.armies_side1 and self.armies_side2:
            self.round += 1
            pos1 = self._next_attacker_pos()
            if pos1 is None:
                break
            army1 = self.armies_side1[pos1]
            if pos1 in self.armies_side2:
                target_pos = pos1
            else:
                target_pos = self._select_target(pos1, self.armies_side2)
            if target_pos is None:
                break
            army2 = self.armies_side2[target_pos]
            sim = GameSimulator(army1, army2, track_stats=False)
            sim.simulate_battle()
            if army1.current_troop_count > 0 and army2.current_troop_count <= 0:
                army1.unit.initial_count = army1.current_troop_count
                del self.armies_side2[target_pos]
            elif army2.current_troop_count > 0 and army1.current_troop_count <= 0:
                army2.unit.initial_count = army2.current_troop_count
                del self.armies_side1[pos1]
            else:
                del self.armies_side1[pos1]
                del self.armies_side2[target_pos]

        if self.armies_side1 and not self.armies_side2:
            self.winner = 1
        elif self.armies_side2 and not self.armies_side1:
            self.winner = 2
        else:
            self.winner = 0

        return {
            "side1": {pos: army.current_troop_count for pos, army in self.armies_side1.items()},
            "side2": {pos: army.current_troop_count for pos, army in self.armies_side2.items()},
        }
