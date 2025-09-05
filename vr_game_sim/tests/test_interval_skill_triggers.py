from vr_game_sim.battlefield_engine import BattlefieldEngine
from typing import Optional

from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army


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
