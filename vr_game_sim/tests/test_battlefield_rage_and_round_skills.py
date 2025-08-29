from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import (
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
)


def make_basic_army(name: str):
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def make_rage_army(name: str) -> Army:
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def make_round_skill_army(name: str) -> Army:
    hero = Hero("Tester", ["talent_godly_wrath"], [], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def test_rage_skill_executes_in_battlefield():
    engine = BattlefieldEngine()
    attacker = make_rage_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    attacker.current_rage = 1000

    engine.engage("A", "B")
    engine.tick(1.0)

    assert attacker.current_rage == 0
    assert attacker.skill_trigger_counts.get("base_skill_snakes_frenzy", 0) == 1
    assert defender.current_troop_count < 1000


def test_chance_per_round_skill_triggers():
    engine = BattlefieldEngine()
    attacker = make_round_skill_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1
    engine.tick(1.0)  # round 2

    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1


def test_defender_attacks_even_if_targeting_other():
    engine = BattlefieldEngine()
    army_a = make_basic_army("A")
    army_b = make_basic_army("B")
    army_c = make_basic_army("C")

    engine.add_army(army_a, "red", position=(100, 0), speed=0)
    engine.add_army(army_b, "red", position=(0, 0), speed=0)
    engine.add_army(army_c, "blue", position=(2, 0), speed=0)

    engine.engage("A", "C")
    engine.engage("B", "C")
    engine.tick(1.0)

    assert army_b.current_troop_count < 1000


def test_defender_rage_skill_targets_only_direct_attacker():
    engine = BattlefieldEngine()
    attacker1 = make_basic_army("A1")
    attacker2 = make_basic_army("A2")
    defender = make_rage_army("D")

    engine.add_army(attacker1, "red", position=(0, 0), speed=0)
    engine.add_army(attacker2, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A1", "D")
    engine.engage("A2", "D")

    engine.tick(1.0)  # start engagements and play first round

    # Reverse engagement processing order so indirect attacker is handled first
    items = list(engine._engagements.items())
    engine._engagements = {items[1][0]: items[1][1], items[0][0]: items[0][1]}

    # Prevent defender from dealing basic or counter damage
    disarm = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_DISARM_DEBUFF, "duration": 5}
    broken = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_BROKEN_BLADE_DEBUFF, "duration": 5}
    defender._create_and_add_single_effect(disarm, "test", defender, defender)
    defender._create_and_add_single_effect(broken, "test", defender, defender)

    a1_before = attacker1.current_troop_count
    a2_before = attacker2.current_troop_count

    defender.current_rage = 1000
    engine.tick(1.0)

    assert attacker1.current_troop_count < a1_before
    assert attacker2.current_troop_count == a2_before

