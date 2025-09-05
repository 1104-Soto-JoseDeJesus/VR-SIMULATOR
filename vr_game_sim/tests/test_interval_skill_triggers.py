from typing import Optional

from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_zero_attack_army(name: str, skill_id: Optional[str] = None, count: int = 10) -> Army:
    hero = Hero("H", [], [], [skill_id], SKILL_REGISTRY_GLOBAL) if skill_id else None
    unit = Unit("pikemen", 5, initial_count=count, initial_atk_modifier=-1.0)
    heroes = [hero] if hero else []
    return Army(name, unit, heroes=heroes)


def setup_engine(skill_id: str):
    attacker = make_zero_attack_army("A", skill_id)
    defender = make_zero_attack_army("B", count=20)
    engine = BattlefieldEngine()
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)
    engine.engage("A", "B")
    return engine, attacker


def test_shield_support_triggers_rounds_9_and_18():
    engine, attacker = setup_engine("plugin_shield_support")
    for rnd in range(1, 19):
        engine.tick(1.0)
        if rnd in (9, 18):
            assert attacker.skill_last_triggered_round.get("plugin_shield_support") == rnd


def test_thors_determination_triggers_rounds_9_and_18():
    engine, attacker = setup_engine("plugin_thors_determination")
    for rnd in range(1, 19):
        engine.tick(1.0)
        if rnd in (9, 18):
            assert attacker.skill_last_triggered_round.get("plugin_thors_determination") == rnd


def test_shield_support_reengage_resets_round_counter():
    attacker = make_zero_attack_army("A", "plugin_shield_support")
    defender1 = make_zero_attack_army("B", count=20)
    defender2 = make_zero_attack_army("C", count=20)
    engine = BattlefieldEngine()
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender1, "blue", position=(2, 0), speed=0)
    engine.add_army(defender2, "blue", position=(-56, 0), speed=0)
    engine.engage("A", "B")
    for _ in range(9):
        engine.tick(1.0)
    assert attacker.skill_last_triggered_round.get("plugin_shield_support") == 9
    engine.engage("A", "C")
    for _ in range(9):
        engine.tick(1.0)
    assert attacker.skill_last_triggered_round.get("plugin_shield_support") == 9


def test_shield_support_single_trigger_multi_engagement():
    defender = make_zero_attack_army("D", "plugin_shield_support", count=20)
    attacker1 = make_zero_attack_army("A", count=20)
    attacker2 = make_zero_attack_army("B", count=20)
    engine = BattlefieldEngine()
    engine.add_army(defender, "red", position=(0, 0), speed=0)
    engine.add_army(attacker1, "blue", position=(2, 0), speed=0)
    engine.add_army(attacker2, "blue", position=(2, 2), speed=0)
    engine.engage("A", "D")
    for _ in range(5):
        engine.tick(1.0)
    engine.engage("B", "D")
    for rnd in range(6, 19):
        engine.tick(1.0)
        if rnd in (9, 18):
            assert defender.skill_last_triggered_round.get("plugin_shield_support") == rnd
    assert defender.skill_trigger_counts.get("plugin_shield_support", 0) == 2
