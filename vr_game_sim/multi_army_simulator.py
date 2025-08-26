"""Simulate battles between multiple armies on a battlefield."""
from __future__ import annotations

from typing import List, Tuple
import random
import math

from .army_composition import Army
from .battlefield import Battlefield, HEX_DIRECTIONS
from .duel import Duel


class MultiArmySimulator:
    """Advance armies on a battlefield and resolve clashes."""

    def __init__(self, battlefield: Battlefield, armies: List[Army]):
        self.battlefield = battlefield
        self.armies = armies
        self.active_duels: List[Duel] = []

    # ------------------------------------------------------------------
    def _clear_targeting(self, army: Army) -> None:
        if army.direct_target and army in army.direct_target.attackers:
            army.direct_target.attackers.remove(army)
        for atk in list(army.attackers):
            atk.direct_target = None
        army.direct_target = None
        army.attackers.clear()

    def _retarget(self, army: Army) -> None:
        if army.direct_target and army.direct_target.current_troop_count <= 0:
            if army in army.direct_target.attackers:
                army.direct_target.attackers.remove(army)
            army.direct_target = None
        if not army.direct_target and army.attackers:
            army.direct_target = random.choice(army.attackers)

    def _set_targeting(self, attacker: Army, defender: Army) -> None:
        if attacker.team == defender.team or attacker.direct_target is defender:
            return
        self._clear_targeting(attacker)
        attacker.direct_target = defender
        if attacker not in defender.attackers:
            defender.attackers.append(attacker)
        if defender.direct_target is None:
            defender.direct_target = attacker

    def _find_open_adjacent(self, defender: Army) -> Tuple[int, int] | None:
        """Return an empty hex adjacent to ``defender`` if one exists."""
        dirs = HEX_DIRECTIONS[:]
        random.shuffle(dirs)
        for dq, dr in dirs:
            q, r = defender.x + dq, defender.y + dr
            if not self.battlefield.within_bounds(q, r):
                continue
            occupied = any(
                a.current_troop_count > 0 and a.x == q and a.y == r for a in self.armies
            )
            if not occupied:
                return q, r
        return None

    def step(self) -> None:
        """Advance one second: move armies, resolve battles and apply results."""
        # Progress ongoing duels round by round
        finished_duels: List[Duel] = []
        for duel in list(self.active_duels):
            # Keep duel simulators in sync with the latest army state so
            # multiple attackers share a defender's current troop counts.
            duel.sync_from_armies()
            duel.allow_b_attack = duel.army_b.direct_target is duel.army_a
            result = duel.simulate_round()
            if not result:
                finished_duels.append(duel)
                continue
            log = result["log"]
            for army, dt, du in result["deltas"]:
                army.apply_round_results(dt, du)
                army.battle_reports.append(log)
            if result["battle_over"]:
                finished_duels.append(duel)

        for duel in finished_duels:
            self.active_duels.remove(duel)
            for army in (duel.army_a, duel.army_b):
                if duel in army.active_duels:
                    army.active_duels.remove(duel)
                if army.current_troop_count <= 0:
                    self._clear_targeting(army)

        # Remove any dead armies while preserving the shared list reference
        # ``BattlefieldTab`` and other callers retain a reference to
        # ``self.armies``.  Reassigning ``self.armies`` to a new list would
        # sever that link, meaning armies added later (e.g. via the GUI) would
        # never be seen by the simulator.  Instead mutate the list in place so
        # all holders see the updated contents.
        self.armies[:] = [a for a in self.armies if a.current_troop_count > 0]

        # Retarget surviving armies
        for army in self.armies:
            self._retarget(army)

        # Move armies not currently in any duel
        for army in self.armies:
            if army.current_troop_count <= 0 or army.active_duels:
                continue
            army.update_position(self.battlefield)

        # Check for clashes based on proximity
        for i, a1 in enumerate(self.armies):
            if a1.current_troop_count <= 0 or a1.active_duels:
                continue
            for a2 in self.armies[i + 1 :]:
                if (
                    a2.current_troop_count <= 0
                    or a2.active_duels
                    or a1.team == a2.team
                ):
                    continue
                dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
                if dist < 1.0:
                    self._set_targeting(a1, a2)
                    allow = a2.direct_target is a1 or a2.direct_target is None
                    duel = Duel(a1, a2, allow_b_attack=allow)
                    self.active_duels.append(duel)
                    a1.active_duels.append(duel)
                    a2.active_duels.append(duel)

        # Final cleanup of dead armies; again, mutate the list in place to keep
        # the simulator and GUI in sync.
        self.armies[:] = [a for a in self.armies if a.current_troop_count > 0]

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        """Start a duel between two armies."""
        if army1.team == army2.team:
            return
        full = True
        duel = Duel(army1, army2, allow_b_attack=full)
        self.active_duels.append(duel)
        army1.active_duels.append(duel)
        army2.active_duels.append(duel)

    def run(self, max_rounds: int = 100) -> List[Army]:
        """Run until only one army remains or max rounds reached."""
        for _ in range(max_rounds):
            if len(self.armies) <= 1:
                break
            self.step()
        return self.armies

    def render_battlefield(self) -> str:
        """Return a textual representation of the battlefield."""
        return self.battlefield.render(self.armies)
