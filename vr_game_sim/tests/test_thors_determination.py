import pytest

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType
from vr_game_sim.constants import (
    EFFECT_NAME_THORS_DETERMINATION_DMG_REDUCTION,
    EFFECT_NAME_THORS_DETERMINATION_BUFF,
)


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


def _prepare_armies():
    hero = Hero("H", [], [], ["plugin_thors_determination"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=100), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=200), heroes=[])
    return army, enemy


def _assert_effect_present(army: Army) -> None:
    dmg_red_effects = [
        e for e in army.effects_to_activate_next_round
        if e.name == EFFECT_NAME_THORS_DETERMINATION_DMG_REDUCTION
    ]
    assert len(dmg_red_effects) == 1
    eff = dmg_red_effects[0]
    assert eff.magnitude == pytest.approx(-0.15)
    assert eff.duration == 2
    # Ensure original buff still scheduled
    assert any(
        e.name == EFFECT_NAME_THORS_DETERMINATION_BUFF
        for e in army.effects_to_activate_next_round
    )


def test_thors_determination_game_simulator():
    army, enemy = _prepare_armies()
    sim = GameSimulator(army, enemy, track_stats=False)
    for _ in range(9):
        _run_round_start(sim)
    _assert_effect_present(army)


def test_thors_determination_battlefield_engine(monkeypatch):
    army, enemy = _prepare_armies()
    monkeypatch.setattr(
        GameSimulator,
        "_calculate_and_log_attack",
        lambda self, a, b, is_counter=False: (0, 0, 0, 0),
    )
    engine = BattlefieldEngine()
    engine.add_army(army, "T1")
    engine.add_army(enemy, "T2")
    engine.engage(army.name, enemy.name)
    for _ in range(9):
        engine.tick(1.0)
    _assert_effect_present(army)


def test_thors_determination_arena_engine(monkeypatch):
    army, enemy = _prepare_armies()
    monkeypatch.setattr(
        GameSimulator,
        "_calculate_and_log_attack",
        lambda self, a, b, is_counter=False: (0, 0, 0, 0),
    )
    engine = ArenaEngine()
    engine.add_army(army, "T1")
    engine.add_army(enemy, "T2")
    engine.engage(army.name, enemy.name)
    for _ in range(9):
        engine.tick(1.0)
    _assert_effect_present(army)

