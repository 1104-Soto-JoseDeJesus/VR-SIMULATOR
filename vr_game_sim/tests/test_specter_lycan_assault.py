from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army


def make_zero_attack_army(name: str, with_talent: bool = False) -> Army:
    hero = None
    if with_talent:
        hero = Hero("Tester", ["talent_specter_lycan_assault"], [], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10, initial_atk_modifier=-1.0)
    heroes = [hero] if hero else []
    return Army(name, unit, heroes=heroes)


def test_specter_lycan_assault_triggers_every_nine_rounds_without_damage():
    engine = BattlefieldEngine()
    attacker = make_zero_attack_army("A", with_talent=True)
    defender = make_zero_attack_army("B")

    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)
    engine.engage("A", "B")

    expected = {9: 1, 18: 2, 27: 3}
    for rnd in range(1, 28):
        engine.tick(1.0)
        if rnd in expected:
            assert attacker.skill_trigger_counts.get("talent_specter_lycan_assault", 0) == expected[rnd]
            assert defender.current_troop_count == 10
            assert attacker.current_troop_count == 10
