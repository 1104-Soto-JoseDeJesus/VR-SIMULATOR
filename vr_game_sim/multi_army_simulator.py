"""Simulate battles between multiple armies on a battlefield."""
from __future__ import annotations

from typing import List, Dict, Tuple
import copy

from .army_composition import Army
from .battlefield import Battlefield
from .game_simulator import GameSimulator


class MultiArmySimulator:
    """Advance armies on a battlefield and resolve clashes."""

    def __init__(self, battlefield: Battlefield, armies: List[Army]):
        self.battlefield = battlefield
        self.armies = armies

    def step(self) -> None:
        """Advance one round: move armies then resolve conflicts."""
        for army in self.armies:
            army.update_position(self.battlefield)

        positions: Dict[Tuple[int, int], List[Army]] = {}
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            positions.setdefault((army.x, army.y), []).append(army)

        for armies_here in positions.values():
            while len(armies_here) > 1:
                a1 = armies_here.pop(0)
                a2 = armies_here.pop(0)
                self._resolve_battle(a1, a2)
                if a1.current_troop_count > 0:
                    armies_here.insert(0, a1)
                if a2.current_troop_count > 0:
                    armies_here.insert(0, a2)

        self.armies = [a for a in self.armies if a.current_troop_count > 0]

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        """Use the existing 1v1 simulator to fight to the death."""
        sim_a = copy.deepcopy(army1)
        sim_b = copy.deepcopy(army2)
        sim_a.unit.initial_count = int(army1.current_troop_count)
        sim_b.unit.initial_count = int(army2.current_troop_count)
        simulator = GameSimulator(sim_a, sim_b, track_stats=False)
        simulator.simulate_battle()
        army1.current_troop_count = sim_a.current_troop_count
        army2.current_troop_count = sim_b.current_troop_count
        army1.unrevivable_troops += sim_a.unrevivable_troops
        army2.unrevivable_troops += sim_b.unrevivable_troops

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
