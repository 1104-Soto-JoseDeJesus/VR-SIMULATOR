from __future__ import annotations
from typing import Dict, Tuple, List, Optional

from .army_composition import Army
from .game_simulator import GameSimulator


class ArenaSimulator:
    """Simple arena simulator supporting up to 5 marches per side on a 2x4 grid."""

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

    def _find_nearest_enemy(
        self, pos: Tuple[int, int], enemies: Dict[Tuple[int, int], Army]
    ) -> Optional[Tuple[int, int]]:
        """Return the position of the nearest enemy army using Manhattan distance."""
        best_pos: Optional[Tuple[int, int]] = None
        best_dist: Optional[int] = None
        for epos in enemies:
            dist = abs(epos[0] - pos[0]) + abs(epos[1] - pos[1])
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_pos = epos
        return best_pos

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
            pos1, army1 = next(iter(self.armies_side1.items()))
            if pos1 in self.armies_side2:
                target_pos = pos1
            else:
                target_pos = self._find_nearest_enemy(pos1, self.armies_side2)
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
