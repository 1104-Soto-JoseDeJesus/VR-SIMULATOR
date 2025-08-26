from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .army_composition import Army
from .game_simulator import GameSimulator
from .report_builder import ReportBuilder


@dataclass
class Duel:
    """Persistent battle state between two armies."""

    army_a: Army
    army_b: Army
    allow_b_attack: bool = True
    report_builder: ReportBuilder = field(default_factory=lambda: ReportBuilder(use_color=False))
    time_acc: float = 0.0

    def __post_init__(self) -> None:
        # Create deep copies for the internal simulator so the original armies
        # retain their positioning and other battlefield state.
        sim_a = copy.deepcopy(self.army_a)
        sim_b = copy.deepcopy(self.army_b)
        sim_a.unit.initial_count = int(self.army_a.current_troop_count)
        sim_b.unit.initial_count = int(self.army_b.current_troop_count)
        # Share skill trigger tracking so multiple duels honour per-round limits
        sim_a.triggered_skills_this_round = self.army_a.triggered_skills_this_round
        sim_b.triggered_skills_this_round = self.army_b.triggered_skills_this_round
        sim_a.skill_last_triggered_round = self.army_a.skill_last_triggered_round
        sim_b.skill_last_triggered_round = self.army_b.skill_last_triggered_round
        self.sim_a = sim_a
        self.sim_b = sim_b
        self.simulator = GameSimulator(sim_a, sim_b, report_builder=self.report_builder, track_stats=False)
        self.simulator.start_battle()
        self.last_a_troops = sim_a.current_troop_count
        self.last_a_unrev = sim_a.unrevivable_troops
        self.last_b_troops = sim_b.current_troop_count
        self.last_b_unrev = sim_b.unrevivable_troops

    # ------------------------------------------------------------------
    def sync_from_armies(self) -> None:
        """Synchronize simulator copies with the real armies.

        When multiple attackers engage the same defender, separate ``Duel``
        instances share the defender.  Without syncing, each duel would use a
        stale snapshot of troop counts, effectively letting the defender fight
        as if losses from other attackers never occurred.  Copy the live
        ``Army`` state into the simulator copies so all duels operate on the
        same data before a round is simulated.
        """

        self.sim_a.current_troop_count = self.army_a.current_troop_count
        self.sim_a.unrevivable_troops = self.army_a.unrevivable_troops
        self.sim_b.current_troop_count = self.army_b.current_troop_count
        self.sim_b.unrevivable_troops = self.army_b.unrevivable_troops
        self.last_a_troops = self.army_a.current_troop_count
        self.last_a_unrev = self.army_a.unrevivable_troops
        self.last_b_troops = self.army_b.current_troop_count
        self.last_b_unrev = self.army_b.unrevivable_troops

    def simulate_round(self, reset_triggers: bool = True) -> Dict[str, Any] | None:
        """Advance the duel by a single round."""
        result = self.simulator.simulate_round(
            allow_army1_attack=True,
            allow_army2_attack=self.allow_b_attack,
            reset_triggers=reset_triggers,
        )
        if not result:
            return None

        delta_a_troops = self.sim_a.current_troop_count - self.last_a_troops
        delta_a_unrev = self.sim_a.unrevivable_troops - self.last_a_unrev
        delta_b_troops = self.sim_b.current_troop_count - self.last_b_troops
        delta_b_unrev = self.sim_b.unrevivable_troops - self.last_b_unrev
        self.last_a_troops = self.sim_a.current_troop_count
        self.last_a_unrev = self.sim_a.unrevivable_troops
        self.last_b_troops = self.sim_b.current_troop_count
        self.last_b_unrev = self.sim_b.unrevivable_troops
        battle_over = self.sim_a.current_troop_count <= 0 or self.sim_b.current_troop_count <= 0
        return {
            "log": result["log"],
            "deltas": [
                (self.army_a, delta_a_troops, delta_a_unrev),
                (self.army_b, delta_b_troops, delta_b_unrev),
            ],
            "battle_over": battle_over,
        }
