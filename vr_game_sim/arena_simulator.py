from __future__ import annotations
import random
import copy
import math
from typing import Dict, Tuple, List, Optional

from .army_composition import Army
from .game_simulator import GameSimulator


class ArenaSimulator:
    """Arena battles on a 2x4 grid for *each* side.

    Armies are placed on a two column by four row grid representing front/back
    ranks across four lanes.  An arena round is a wave of engagements where
    each surviving army may attack **any** enemy following the targeting
    priorities.  Multiple armies can focus the same target within the same
    round; battles are resolved in a deterministic row-major order to model a
    fully open battlefield with dynamic targeting.

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

    def __init__(
        self,
        armies_side1: List[Army],
        armies_side2: List[Army],
        debug: bool = False,
    ) -> None:
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
        self.debug: bool = debug
        self.last_round_buffer: List[
            Tuple[Tuple[int, int], Tuple[int, int], float, float]
        ] = []

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
        """Simulate the arena until one side is eliminated.

        Each battle round is resolved concurrently: all surviving armies pick
        their targets based on the starting snapshot of that round.  Every
        attacker/defender pair is then simulated on deep copies and the losses
        for both armies are recorded.  Only after all engagements have been
        processed are the aggregated losses applied to the live armies.  This
        models a fully open battlefield where damage from multiple attackers is
        combined before any army is removed.
        """

        for army in list(self.armies_side1.values()) + list(self.armies_side2.values()):
            army.reset_for_new_battle()

        while self.armies_side1 and self.armies_side2:
            self.round += 1

            # Determine all attack plans for this round using a snapshot of the
            # current battlefield.  No army state is modified until all
            # engagements are processed.
            plans: List[Tuple[int, Tuple[int, int], Tuple[int, int]]] = []
            snapshot1 = self.armies_side1.copy()
            snapshot2 = self.armies_side2.copy()

            for pos in self._position_order():
                if pos in snapshot1:
                    target = self._select_target(pos, snapshot2)
                    if target is not None:
                        plans.append((1, pos, target))
            for pos in self._position_order():
                if pos in snapshot2:
                    target = self._select_target(pos, snapshot1)
                    if target is not None:
                        plans.append((2, pos, target))

            if not plans:
                break

            round_buffer: List[Tuple[Tuple[int, int], Tuple[int, int], float, float]] = []
            losses1: Dict[Tuple[int, int], float] = {}
            losses2: Dict[Tuple[int, int], float] = {}

            # Resolve each engagement on copies and accumulate troop losses.
            for side, apos, dpos in plans:
                if side == 1:
                    atk = self.armies_side1.get(apos)
                    defender = self.armies_side2.get(dpos)
                else:
                    atk = self.armies_side2.get(apos)
                    defender = self.armies_side1.get(dpos)
                if atk is None or defender is None:
                    continue
                atk_copy = copy.deepcopy(atk)
                def_copy = copy.deepcopy(defender)
                sim = GameSimulator(atk_copy, def_copy, track_stats=False)
                sim.simulate_battle()

                atk_loss = max(0.0, atk.current_troop_count - atk_copy.current_troop_count)
                def_loss = max(0.0, defender.current_troop_count - def_copy.current_troop_count)
                if side == 1:
                    losses1[apos] = losses1.get(apos, 0.0) + atk_loss
                    losses2[dpos] = losses2.get(dpos, 0.0) + def_loss
                else:
                    losses2[apos] = losses2.get(apos, 0.0) + atk_loss
                    losses1[dpos] = losses1.get(dpos, 0.0) + def_loss
                round_buffer.append((apos, dpos, atk_copy.current_troop_count, def_copy.current_troop_count))

            # Apply the accumulated losses to the live armies simultaneously.
            for pos, loss in losses1.items():
                army = self.armies_side1.get(pos)
                if army is None:
                    continue
                army.current_troop_count = max(0.0, army.current_troop_count - loss)
                if army.current_troop_count > 0:
                    army.unit.initial_count = army.current_troop_count
                else:
                    del self.armies_side1[pos]
            for pos, loss in losses2.items():
                army = self.armies_side2.get(pos)
                if army is None:
                    continue
                army.current_troop_count = max(0.0, army.current_troop_count - loss)
                if army.current_troop_count > 0:
                    army.unit.initial_count = army.current_troop_count
                else:
                    del self.armies_side2[pos]

            self.last_round_buffer = round_buffer

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
