import random

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType


def _run_round_start(sim: GameSimulator) -> None:
    sim.round += 1
    for army in (sim.army1, sim.army2):
        if army.effects_to_activate_next_round:
            army.upcoming_effects.extend(army.effects_to_activate_next_round)
            army.effects_to_activate_next_round.clear()
        army.activate_queued_effects()
        army.decrement_effect_durations()
    sim.army1.started_last_round_with_active_shield = sim.army1.started_round_with_active_shield
    sim.army2.started_last_round_with_active_shield = sim.army2.started_round_with_active_shield
    sim.army1.started_round_with_active_shield = sim.army1.get_current_shield_hp() > 0
    sim.army2.started_round_with_active_shield = sim.army2.get_current_shield_hp() > 0
    for army, opponent in ((sim.army1, sim.army2), (sim.army2, sim.army1)):
        if army.current_troop_count <= 0:
            continue
        army.activate_queued_effects()
        army.apply_start_of_round_rage_deductions()
        army.process_periodic_effects("start_of_round", opponent=opponent)
        army.activate_queued_effects()
        sim._process_skill_triggers(
            army,
            opponent,
            SkillTriggerType.CHANCE_PER_ROUND,
            event_data={"opponent_for_shield_calc": opponent},
        )
        army.activate_queued_effects()


def test_shield_flag_consistency_across_modes(monkeypatch):
    hero = Hero("H", [], [], [], SKILL_REGISTRY_GLOBAL)
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])

    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    shield_phase = {id(army): 1}

    def fake_shield(self: Army) -> float:
        return 100.0 if shield_phase.get(id(self), 0) == 1 else 0.0

    monkeypatch.setattr(Army, "get_current_shield_hp", fake_shield)

    sim = GameSimulator(army, enemy, track_stats=False)
    _run_round_start(sim)
    assert army.started_round_with_active_shield
    shield_phase[id(army)] = 0
    _run_round_start(sim)
    assert army.started_last_round_with_active_shield and not army.started_round_with_active_shield

    army_b = Army("AB", Unit("pikemen", 5, initial_count=10), heroes=[Hero("HB", [], [], [], SKILL_REGISTRY_GLOBAL)])
    enemy_b = Army("EB", Unit("archers", 5, initial_count=10), heroes=[])
    shield_phase[id(army_b)] = 1
    engine = BattlefieldEngine()
    monkeypatch.setattr(GameSimulator, "_calculate_and_log_attack", lambda self, a, b, is_counter=False: (0,0,0,0))
    engine.add_army(army_b, "T1")
    engine.add_army(enemy_b, "T2")
    engine.engage("AB", "EB")
    engine.tick(1.0)
    assert army_b.started_round_with_active_shield
    shield_phase[id(army_b)] = 0
    engine.tick(1.0)
    assert army_b.started_last_round_with_active_shield and not army_b.started_round_with_active_shield


def test_shield_attacker_consistent_across_modes(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["plugin_shield_attacker"], SKILL_REGISTRY_GLOBAL)
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])

    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    shield_initial = {id(army): True}
    shield_calls = {}

    def fake_shield(self: Army) -> float:
        cid = id(self)
        count = shield_calls.get(cid, 0)
        shield_calls[cid] = count + 1
        if shield_initial.get(cid, False) and count < 5:
            return 100.0
        return 0.0

    monkeypatch.setattr(Army, "get_current_shield_hp", fake_shield)
    sim = GameSimulator(army, enemy, track_stats=False)
    _run_round_start(sim)
    sim._process_skill_triggers(
        army,
        enemy,
        SkillTriggerType.ON_BASIC_ATTACK,
        event_data={"opponent_for_shield_calc": enemy},
    )
    assert "plugin_shield_attacker" in army.triggered_skills_this_round

    army_b = Army("AB", Unit("pikemen", 5, initial_count=10), heroes=[Hero("HB", [], [], ["plugin_shield_attacker"], SKILL_REGISTRY_GLOBAL)])
    enemy_b = Army("EB", Unit("archers", 5, initial_count=10), heroes=[])
    shield_initial[id(army_b)] = True
    engine = BattlefieldEngine()
    engine.add_army(army_b, "T1")
    engine.add_army(enemy_b, "T2")
    engine.engage("AB", "EB")
    engine.tick(1.0)
    assert "plugin_shield_attacker" in army_b.triggered_skills_this_round
