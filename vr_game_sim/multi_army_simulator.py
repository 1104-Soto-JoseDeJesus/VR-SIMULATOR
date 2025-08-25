"""Simulate battles between multiple armies on a battlefield."""
from __future__ import annotations

from typing import List, Dict, Tuple
import copy

from .army_composition import Army
from .battlefield import Battlefield, step_towards
from .game_simulator import GameSimulator


class MultiArmySimulator:
    """Advance armies on a battlefield and resolve clashes."""

    def __init__(self, battlefield: Battlefield, armies: List[Army]):
        self.battlefield = battlefield
        self.armies = armies

    def step(self) -> None:
        """Advance one second: move armies, resolve battles and apply results."""
        # Progress ongoing battles
        for army in self.armies:
            army.progress_battle()
        self.armies = [a for a in self.armies if a.current_troop_count > 0]

        # Move armies that are not currently fighting
        for army in self.armies:
            if army.current_troop_count > 0 and army.battle_time_remaining == 0:
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
                        if occupant.battle_time_remaining == 0:
                            self._resolve_battle(army, occupant)
                        continue
                army.update_position(self.battlefield)

        # Battles for armies ending up on the same tile
        positions: Dict[Tuple[int, int], List[Army]] = {}
        for army in self.armies:
            if army.current_troop_count <= 0 or army.battle_time_remaining > 0:
                continue
            positions.setdefault((army.x, army.y), []).append(army)

        for armies_here in positions.values():
            while len(armies_here) > 1:
                a1 = armies_here.pop(0)
                a2 = armies_here.pop(0)
                if a1.team != a2.team:
                    self._resolve_battle(a1, a2)
                    if a1.current_troop_count > 0 and a1.battle_time_remaining == 0:
                        armies_here.insert(0, a1)
                    if a2.current_troop_count > 0 and a2.battle_time_remaining == 0:
                        armies_here.insert(0, a2)

        self.armies = [a for a in self.armies if a.current_troop_count > 0]

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        """Use the existing 1v1 simulator to fight to the death."""
        sim_a = copy.deepcopy(army1)
        sim_b = copy.deepcopy(army2)
        sim_a.unit.initial_count = int(army1.current_troop_count)
        sim_b.unit.initial_count = int(army2.current_troop_count)
        from .report_builder import ReportBuilder

        rb = ReportBuilder(use_color=False)
        simulator = GameSimulator(sim_a, sim_b, report_builder=rb, track_stats=False)
        simulator.simulate_battle()
        duration = simulator.round
        report_text = rb.get_report_text()
        army1.battle_reports.append(report_text)
        army2.battle_reports.append(report_text)
        army1.engage(sim_a.current_troop_count, sim_a.unrevivable_troops, duration)
        army2.engage(sim_b.current_troop_count, sim_b.unrevivable_troops, duration)

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
