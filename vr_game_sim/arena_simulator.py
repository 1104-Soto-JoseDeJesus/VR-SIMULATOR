from __future__ import annotations
import random
from typing import Dict, Tuple, List, Optional

from .army_composition import Army
from .game_simulator import GameSimulator


class ArenaSimulator:
    """Arena battles on a 2x4 grid for *each* side.

    Both attackers and defenders can field armies on their own two column by
    four row grid.  Columns represent the front and back ranks while rows are
    lanes from top to bottom.  In contrast to the previous sequential
    implementation, all available armies engage their targets **simultaneously**
    each round.  A round therefore represents one wave of pairwise battles.

    Target selection favours enemies in the same lane as the attacker.  If the
    lane is empty, columns are inspected by proximity starting with the
    attacker's column and scanning lanes from the front towards the back.
    """

    GRID_COLS = 2
    GRID_ROWS = 4

    @staticmethod
    def choose_reactive_trigger(
        attackers: List[Army],
        defender_target: Optional[Army],
    ) -> Army:
        """Select which attacking army's reactive trigger should resolve.

        If the defender is directly attacking one of the armies that hit it in the
        current round, that army's trigger takes priority. Otherwise one of the
        attackers is chosen at random.

        Parameters
        ----------
        attackers:
            List of armies that successfully hit the defender this round.
        defender_target:
            The army the defender is directly attacking this round, or ``None`` if
            the defender is not currently attacking any of the attackers.
        """

        if defender_target and defender_target in attackers:
            return defender_target
        return random.choice(attackers)

    def __init__(self, armies_side1: List[Army], armies_side2: List[Army]):
        max_slots = self.GRID_COLS * self.GRID_ROWS
        if len(armies_side1) > max_slots or len(armies_side2) > max_slots:
            raise ValueError(
                f"ArenaSimulator supports at most {max_slots} armies per side"
            )

        # Store armies keyed by their (col, row) position
        self.armies_side1: Dict[Tuple[int, int], Army] = {
            army.position: army for army in armies_side1 if army.position is not None
        }
        self.armies_side2: Dict[Tuple[int, int], Army] = {
            army.position: army for army in armies_side2 if army.position is not None
        }
        self.round: int = 0
        self.winner: Optional[int] = None

    def _position_order(self) -> List[Tuple[int, int]]:
        """Return grid positions in row-major order, front column first."""
        order: List[Tuple[int, int]] = []
        for row in range(self.GRID_ROWS):
            for col in range(self.GRID_COLS):
                order.append((col, row))
        return order

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
        """Run waves of simultaneous battles until one side runs out of armies.

        Each round all available armies choose targets according to the arena
        targeting rules.  Paired armies fight concurrently using
        ``GameSimulator``. The winning army in each pair keeps its remaining
        troops and may fight again in subsequent rounds. The function returns a
        mapping of surviving troops per position for both sides.
        """
        # Ensure armies start fresh
        for army in list(self.armies_side1.values()) + list(self.armies_side2.values()):
            army.reset_for_new_battle()

        while self.armies_side1 and self.armies_side2:
            self.round += 1

            # Determine pairings for this round. Each army can participate at most
            # once per round to model simultaneous engagements.
            available1 = set(self.armies_side1.keys())
            available2 = set(self.armies_side2.keys())
            pairs: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []

            order = self._position_order()

            for pos1 in order:
                if pos1 not in available1:
                    continue
                target = self._select_target(pos1, {p: self.armies_side2[p] for p in available2})
                if target is not None:
                    pairs.append((pos1, target))
                    available1.remove(pos1)
                    available2.remove(target)

            for pos2 in order:
                if pos2 not in available2:
                    continue
                target = self._select_target(pos2, {p: self.armies_side1[p] for p in available1})
                if target is not None:
                    pairs.append((target, pos2))
                    available1.remove(target)
                    available2.remove(pos2)

            if not pairs:
                break

            # Resolve all battles for the current round
            for pos1, pos2 in pairs:
                army1 = self.armies_side1[pos1]
                army2 = self.armies_side2[pos2]
                sim = GameSimulator(army1, army2, track_stats=False)
                sim.simulate_battle()
                if army1.current_troop_count > 0 and army2.current_troop_count <= 0:
                    army1.unit.initial_count = army1.current_troop_count
                    del self.armies_side2[pos2]
                elif army2.current_troop_count > 0 and army1.current_troop_count <= 0:
                    army2.unit.initial_count = army2.current_troop_count
                    del self.armies_side1[pos1]
                else:
                    del self.armies_side1[pos1]
                    del self.armies_side2[pos2]

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
