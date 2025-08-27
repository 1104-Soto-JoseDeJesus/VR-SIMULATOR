from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

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
        """Initialise the duel using the live ``Army`` objects.

        Prior versions deep‑copied the armies so simultaneous attackers
        operated on isolated snapshots that required manual synchronisation.
        By referencing the original armies directly the combat state (effects,
        shields, troop counts, etc.) is naturally shared between concurrent
        duels.
        """

        # ``GameSimulator`` mutates the ``Army`` instances it receives, so by
        # passing the real armies we guarantee all duels operate on a single
        # source of truth.
        self.simulator = GameSimulator(
            self.army_a, self.army_b, report_builder=self.report_builder, track_stats=False
        )

        # Align the simulator's round counter with battlefield time so that
        # late‑joining attackers start on the correct global round.
        self.simulator.round = max(self.army_a.continuous_rounds, self.army_b.continuous_rounds)

    def simulate_round(self, reset_triggers: bool = True) -> Dict[str, Any] | None:
        """Advance the duel by a single round.

        The armies are mutated in place, so to provide round deltas we snapshot
        their state before and after running the simulator.
        """

        # Ensure any shared ``Army`` objects reference this duel's simulator so
        # skill logic that calls ``army.simulator`` interacts with the correct
        # ``GameSimulator`` instance.
        self.simulator.army1.simulator = self.simulator
        self.simulator.army2.simulator = self.simulator

        start_a_troops = self.army_a.current_troop_count
        start_a_unrev = self.army_a.unrevivable_troops
        start_b_troops = self.army_b.current_troop_count
        start_b_unrev = self.army_b.unrevivable_troops

        result = self.simulator.simulate_round(
            allow_army1_attack=True,
            allow_army2_attack=self.allow_b_attack,
            reset_triggers=reset_triggers,
        )
        if not result:
            return None

        delta_a_troops = self.army_a.current_troop_count - start_a_troops
        delta_a_unrev = self.army_a.unrevivable_troops - start_a_unrev
        delta_b_troops = self.army_b.current_troop_count - start_b_troops
        delta_b_unrev = self.army_b.unrevivable_troops - start_b_unrev
        battle_over = self.army_a.current_troop_count <= 0 or self.army_b.current_troop_count <= 0
        return {
            "log": result["log"],
            "deltas": [
                (self.army_a, delta_a_troops, delta_a_unrev),
                (self.army_b, delta_b_troops, delta_b_unrev),
            ],
            "battle_over": battle_over,
        }
