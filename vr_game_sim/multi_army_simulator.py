"""Simulate battles between multiple armies on a battlefield."""
from __future__ import annotations

from typing import List, Dict, Tuple
import random

from .army_composition import Army
from .battlefield import Battlefield, step_towards, hex_distance
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
        if attacker.direct_target is defender:
            return
        self._clear_targeting(attacker)
        attacker.direct_target = defender
        if attacker not in defender.attackers:
            defender.attackers.append(attacker)
        if defender.direct_target is None:
            defender.direct_target = attacker

    def step(self) -> None:
        """Advance one second: move armies, resolve battles and apply results."""
        # Progress ongoing duels round by round
        finished_duels: List[Duel] = []
        for duel in list(self.active_duels):
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

        # Remove any dead armies
        self.armies = [a for a in self.armies if a.current_troop_count > 0]

        # Retarget surviving armies
        for army in self.armies:
            self._retarget(army)

        # Move armies not currently in any duel
        for army in self.armies:
            if army.current_troop_count <= 0 or army.active_duels:
                continue
            if army.destination:
                step = step_towards(self.battlefield, (army.x, army.y), army.destination)
                occupant = next(
                    (
                        a
                        for a in self.armies
                        if a is not army
                        and a.current_troop_count > 0
                        and a.x == step[0]
                        and a.y == step[1]
                    ),
                    None,
                )
                if occupant and occupant.team != army.team:
                    self._set_targeting(army, occupant)
                    full = occupant.direct_target is army or occupant.direct_target is None
                    duel = Duel(army, occupant, allow_b_attack=full)
                    self.active_duels.append(duel)
                    army.active_duels.append(duel)
                    occupant.active_duels.append(duel)
                    continue
            army.update_position(self.battlefield)

        # Handle armies ending up on same tile after movement
        positions: Dict[Tuple[int, int], List[Army]] = {}
        for army in self.armies:
            if army.current_troop_count <= 0 or army.active_duels:
                continue
            positions.setdefault((army.x, army.y), []).append(army)

        for armies_here in positions.values():
            while len(armies_here) > 1:
                a1 = armies_here.pop(0)
                a2 = armies_here.pop(0)
                if a1.team != a2.team:
                    self._set_targeting(a1, a2)
                    duel = Duel(a1, a2)
                    self.active_duels.append(duel)
                    a1.active_duels.append(duel)
                    a2.active_duels.append(duel)
                    if a1.current_troop_count > 0:
                        armies_here.insert(0, a1)
                    if a2.current_troop_count > 0:
                        armies_here.insert(0, a2)

        self.armies = [a for a in self.armies if a.current_troop_count > 0]

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        """Start a duel between two armies."""
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
