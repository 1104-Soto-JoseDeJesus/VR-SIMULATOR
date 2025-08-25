from __future__ import annotations
import random
import copy
import math
from typing import Dict, Tuple, List, Optional, Set

from .army_composition import Army
from .game_simulator import GameSimulator


class ArenaSimulator:
    """Arena battles on a 2x4 grid for *each* side.

    Armies are placed on a two column by four row grid representing front/back
    ranks across four lanes.  An arena round is a wave of engagements where
    each surviving army may attack **any** enemy following slot specific target
    priorities.  Multiple armies can focus the same target within the same
    round; battles are resolved in a deterministic row-major order to model a
    fully open battlefield with dynamic targeting.

    Targeting does not consider geometric proximity.  Instead each slot has a
    predefined list of opposing slots it will attempt to strike, skipping any
    positions that are empty or contain defeated armies.
    """

    GRID_COLS = 2
    GRID_ROWS = 4

    # Mapping between slot numbers and grid positions for both sides.  The
    # "left" side is mirrored horizontally compared to the "right" side.
    LEFT_SLOT_TO_POS = {
        1: (1, 0),
        2: (0, 0),
        3: (1, 1),
        4: (0, 1),
        5: (1, 2),
        6: (0, 2),
        7: (1, 3),
        8: (0, 3),
    }
    RIGHT_SLOT_TO_POS = {
        1: (0, 0),
        2: (1, 0),
        3: (0, 1),
        4: (1, 1),
        5: (0, 2),
        6: (1, 2),
        7: (0, 3),
        8: (1, 3),
    }
    LEFT_POS_TO_SLOT = {v: k for k, v in LEFT_SLOT_TO_POS.items()}
    RIGHT_POS_TO_SLOT = {v: k for k, v in RIGHT_SLOT_TO_POS.items()}

    LEFT_TARGET_PRIORITY = {
        1: [1, 2, 3, 4, 5, 6, 7, 8],
        2: [1, 2, 3, 4, 5, 6, 7, 8],
        3: [3, 4, 5, 6, 7, 8, 1, 2],
        4: [3, 4, 5, 6, 7, 8, 1, 2],
        5: [5, 6, 7, 8, 3, 4, 1, 2],
        6: [5, 6, 7, 8, 3, 4, 1, 2],
        7: [7, 8, 5, 6, 3, 4, 1, 2],
        8: [7, 8, 5, 6, 3, 4, 1, 2],
    }
    RIGHT_TARGET_PRIORITY = {
        1: [1, 2, 3, 4, 5, 6, 7, 8],
        2: [1, 2, 3, 4, 5, 6, 7, 8],
        3: [3, 4, 1, 2, 5, 6, 7, 8],
        4: [3, 4, 1, 2, 5, 6, 7, 8],
        5: [5, 6, 3, 4, 1, 2, 7, 8],
        6: [5, 6, 3, 4, 1, 2, 7, 8],
        7: [7, 8, 5, 6, 3, 4, 1, 2],
        8: [7, 8, 5, 6, 3, 4, 1, 2],
    }

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

    def _determine_reactive_choices(
        self, plans: List[Tuple[int, Tuple[int, int], Tuple[int, int]]]
    ) -> Dict[Tuple[int, Tuple[int, int]], Tuple[int, Tuple[int, int]]]:
        """Select which attacker may trigger reactive skills for each defender.

        Parameters
        ----------
        plans:
            List of ``(side, attacker_pos, defender_pos)`` tuples for the round.

        Returns
        -------
        Mapping from ``(defender_side, defender_pos)`` to the chosen attacker
        tuple ``(attacker_side, attacker_pos)``.  Attackers not returned in this
        mapping will have the defender's reactive skills suppressed for that
        engagement.
        """

        attack_target_map: Dict[Tuple[int, Tuple[int, int]], Tuple[int, int]] = {
            (side, apos): dpos for side, apos, dpos in plans
        }
        attackers_by_defender: Dict[
            Tuple[int, Tuple[int, int]], List[Tuple[int, Tuple[int, int]]]
        ] = {}
        for side, apos, dpos in plans:
            def_side = 2 if side == 1 else 1
            attackers_by_defender.setdefault((def_side, dpos), []).append((side, apos))

        reactive_choice: Dict[Tuple[int, Tuple[int, int]], Tuple[int, Tuple[int, int]]] = {}
        for (def_side, dpos), attackers in attackers_by_defender.items():
            defender_army = (
                self.armies_side1.get(dpos)
                if def_side == 1
                else self.armies_side2.get(dpos)
            )
            if defender_army is None:
                continue
            defender_target_pos = attack_target_map.get((def_side, dpos))
            defender_target_army = None
            if defender_target_pos is not None:
                defender_target_army = (
                    self.armies_side2.get(defender_target_pos)
                    if def_side == 1
                    else self.armies_side1.get(defender_target_pos)
                )
            attacker_armies: List[Army] = []
            for att_side, apos in attackers:
                army = (
                    self.armies_side1.get(apos)
                    if att_side == 1
                    else self.armies_side2.get(apos)
                )
                if army is not None:
                    attacker_armies.append(army)
            if not attacker_armies:
                continue
            chosen = self.choose_reactive_trigger(attacker_armies, defender_target_army)
            for att_side, apos in attackers:
                army = (
                    self.armies_side1.get(apos)
                    if att_side == 1
                    else self.armies_side2.get(apos)
                )
                if army is chosen:
                    reactive_choice[(def_side, dpos)] = (att_side, apos)
                    break

        return reactive_choice

    def _position_order(self, side: int) -> List[Tuple[int, int]]:
        """Return positions in slot-number order for the given ``side``.

        The arena uses the numbering shown in the design diagram: slots ``1``–``8``
        run down the rows, with the left side mirrored horizontally compared to
        the right side.  Iterating in this order guarantees deterministic attack
        resolution and makes the slot/coordinate relationship explicit.
        """

        mapping = self.LEFT_SLOT_TO_POS if side == 1 else self.RIGHT_SLOT_TO_POS
        return [mapping[i] for i in range(1, 9)]

    def _compute_round_plans(self) -> List[Tuple[int, Tuple[int, int], Tuple[int, int]]]:
        """Compute all attack plans for the current round.

        Each occupied slot is visited at most once ensuring a unit can only
        select a single target in a round.  The plans are returned as a list of
        tuples ``(side, attacker_pos, defender_pos)``.
        """

        plans: List[Tuple[int, Tuple[int, int], Tuple[int, int]]] = []
        snapshot1 = self.armies_side1.copy()
        snapshot2 = self.armies_side2.copy()

        for pos in self._position_order(1):
            if pos in snapshot1:
                target = self._select_target(1, pos, snapshot2)
                if target is not None:
                    plans.append((1, pos, target))
        for pos in self._position_order(2):
            if pos in snapshot2:
                target = self._select_target(2, pos, snapshot1)
                if target is not None:
                    plans.append((2, pos, target))

        return plans

    def _select_target(
        self,
        side: int,
        pos: Tuple[int, int],
        enemies: Dict[Tuple[int, int], Army],
    ) -> Optional[Tuple[int, int]]:
        """Return the target position following predefined slot priorities."""

        if side == 1:
            pos_to_slot = self.LEFT_POS_TO_SLOT
            slot_to_pos = self.RIGHT_SLOT_TO_POS
            priorities = self.LEFT_TARGET_PRIORITY
        else:
            pos_to_slot = self.RIGHT_POS_TO_SLOT
            slot_to_pos = self.LEFT_SLOT_TO_POS
            priorities = self.RIGHT_TARGET_PRIORITY

        slot = pos_to_slot.get(pos)
        if slot is None:
            return None

        for target_slot in priorities[slot]:
            target_pos = slot_to_pos[target_slot]
            if target_pos in enemies:
                return target_pos
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

            round_buffer: List[Tuple[Tuple[int, int], Tuple[int, int], float, float]] = []
            losses1: Dict[Tuple[int, int], float] = {}
            losses2: Dict[Tuple[int, int], float] = {}

            # Snapshots track remaining troops mid-round so attackers can
            # retarget if a slot is wiped out before their turn.
            snapshot1: Dict[Tuple[int, int], float] = {
                pos: army.current_troop_count for pos, army in self.armies_side1.items()
            }
            snapshot2: Dict[Tuple[int, int], float] = {
                pos: army.current_troop_count for pos, army in self.armies_side2.items()
            }

            plans = self._compute_round_plans()
            reactive_choice = self._determine_reactive_choices(plans)
            reactive_triggered: Set[Tuple[int, Tuple[int, int]]] = set()

            # Side 1 attacks in slot order
            for apos in self._position_order(1):
                if apos not in snapshot1:
                    continue
                target_pos = self._select_target(1, apos, dict.fromkeys(snapshot2.keys()))
                if target_pos is None:
                    continue
                atk = self.armies_side1.get(apos)
                defender = self.armies_side2.get(target_pos)
                if atk is None or defender is None:
                    continue

                atk_copy = copy.deepcopy(atk)
                def_copy = copy.deepcopy(defender)
                key = (2, target_pos)
                allow_reactive = reactive_choice.get(key) == (1, apos) and key not in reactive_triggered
                if not allow_reactive:
                    def_copy.reactive_triggers_blocked = True
                sim = GameSimulator(atk_copy, def_copy, track_stats=False)
                sim.simulate_battle()

                atk_loss = max(0.0, atk.current_troop_count - atk_copy.current_troop_count)
                def_loss = max(0.0, defender.current_troop_count - def_copy.current_troop_count)

                losses1[apos] = losses1.get(apos, 0.0) + atk_loss
                losses2[target_pos] = losses2.get(target_pos, 0.0) + def_loss
                round_buffer.append((apos, target_pos, atk_copy.current_troop_count, def_copy.current_troop_count))
                if allow_reactive:
                    reactive_triggered.add(key)

                # Update snapshots so later attackers see the casualties
                remaining_atk = snapshot1.get(apos, 0.0) - atk_loss
                if remaining_atk > 0:
                    snapshot1[apos] = remaining_atk
                else:
                    snapshot1.pop(apos, None)
                remaining_def = snapshot2.get(target_pos, 0.0) - def_loss
                if remaining_def > 0:
                    snapshot2[target_pos] = remaining_def
                else:
                    snapshot2.pop(target_pos, None)

            # Side 2 attacks using the updated snapshots
            for apos in self._position_order(2):
                if apos not in snapshot2:
                    continue
                target_pos = self._select_target(2, apos, dict.fromkeys(snapshot1.keys()))
                if target_pos is None:
                    continue
                atk = self.armies_side2.get(apos)
                defender = self.armies_side1.get(target_pos)
                if atk is None or defender is None:
                    continue

                atk_copy = copy.deepcopy(atk)
                def_copy = copy.deepcopy(defender)
                key = (1, target_pos)
                allow_reactive = reactive_choice.get(key) == (2, apos) and key not in reactive_triggered
                if not allow_reactive:
                    def_copy.reactive_triggers_blocked = True
                sim = GameSimulator(atk_copy, def_copy, track_stats=False)
                sim.simulate_battle()

                atk_loss = max(0.0, atk.current_troop_count - atk_copy.current_troop_count)
                def_loss = max(0.0, defender.current_troop_count - def_copy.current_troop_count)

                losses2[apos] = losses2.get(apos, 0.0) + atk_loss
                losses1[target_pos] = losses1.get(target_pos, 0.0) + def_loss
                round_buffer.append((apos, target_pos, atk_copy.current_troop_count, def_copy.current_troop_count))
                if allow_reactive:
                    reactive_triggered.add(key)

                remaining_atk = snapshot2.get(apos, 0.0) - atk_loss
                if remaining_atk > 0:
                    snapshot2[apos] = remaining_atk
                else:
                    snapshot2.pop(apos, None)
                remaining_def = snapshot1.get(target_pos, 0.0) - def_loss
                if remaining_def > 0:
                    snapshot1[target_pos] = remaining_def
                else:
                    snapshot1.pop(target_pos, None)

            if not round_buffer:
                break

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
