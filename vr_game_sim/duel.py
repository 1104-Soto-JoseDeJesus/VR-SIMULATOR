from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Any

from .army_composition import Army
from .game_simulator import GameSimulator
from .report_builder import ReportBuilder


def _copy_battle_state(src: Army, dest: Army) -> None:
    """Deep-copy combat-relevant fields from ``src`` into ``dest``."""
    dest.active_effects = copy.deepcopy(src.active_effects)
    dest.upcoming_effects = copy.deepcopy(src.upcoming_effects)
    dest.effects_to_activate_next_round = copy.deepcopy(src.effects_to_activate_next_round)
    dest.current_rage = src.current_rage
    dest.pending_hp_damage_this_round = src.pending_hp_damage_this_round
    dest.pending_hp_healing_this_round = src.pending_hp_healing_this_round
    dest.started_round_with_active_shield = src.started_round_with_active_shield
    dest.started_last_round_with_active_shield = src.started_last_round_with_active_shield
    dest.rage_added_this_round = src.rage_added_this_round
    dest.shield_hp_gained_this_round = src.shield_hp_gained_this_round
    dest.army_used_rage_skill_this_round_for_rage_gain_block = (
        src.army_used_rage_skill_this_round_for_rage_gain_block
    )
    dest.base_rage_awarded_this_round = src.base_rage_awarded_this_round
    dest.healing_hymn_triggered_this_round = src.healing_hymn_triggered_this_round
    dest.hero1_rage_skill_queued_this_round = src.hero1_rage_skill_queued_this_round
    dest.hero1_rage_skill_used_round = src.hero1_rage_skill_used_round
    dest.hero2_rage_skill_primed_for_round = src.hero2_rage_skill_primed_for_round
    dest.hero1_rage_skill_cast_blocked_by_silence_this_round = (
        src.hero1_rage_skill_cast_blocked_by_silence_this_round
    )
    dest.damage_dealt_history = list(src.damage_dealt_history)
    dest.heal_received_history = list(src.heal_received_history)
    dest.shield_received_history = list(src.shield_received_history)
    dest.rage_gained_history = list(src.rage_gained_history)


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
        _copy_battle_state(self.army_a, self.sim_a)
        _copy_battle_state(self.army_b, self.sim_b)
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
        _copy_battle_state(self.sim_a, self.army_a)
        _copy_battle_state(self.sim_b, self.army_b)
        battle_over = self.sim_a.current_troop_count <= 0 or self.sim_b.current_troop_count <= 0
        return {
            "log": result["log"],
            "deltas": [
                (self.army_a, delta_a_troops, delta_a_unrev),
                (self.army_b, delta_b_troops, delta_b_unrev),
            ],
            "battle_over": battle_over,
        }
