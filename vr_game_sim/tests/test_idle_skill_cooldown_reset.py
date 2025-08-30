from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def _make_hold_fast_army(name: str) -> Army:
    hero = Hero("Tester", ["talent_hold_fast"], [], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def _make_basic_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def _run_cooldown_reset_scenario(engine):
    skill_def = SKILL_REGISTRY_GLOBAL["talent_hold_fast"]
    orig_chance = skill_def.get("trigger_chance", 0.0)
    skill_def["trigger_chance"] = 1.0
    try:
        attacker = _make_basic_army("A")
        defender = _make_hold_fast_army("B")
        engine.add_army(attacker, "red", position=(0, 0), speed=0)
        engine.add_army(defender, "blue", position=(2, 0), speed=0)

        engine.engage("A", "B")
        engine.tick(1.0)
        assert defender.skill_trigger_counts.get("talent_hold_fast", 0) == 1

        engine.set_direct_target("A", None)
        engine.tick(0.9)
        engine.tick(0.1)

        engine.engage("A", "B")
        engine.tick(1.0)
        assert defender.skill_trigger_counts.get("talent_hold_fast", 0) == 2
    finally:
        skill_def["trigger_chance"] = orig_chance


def test_battlefield_cooldown_resets_after_idle():
    _run_cooldown_reset_scenario(BattlefieldEngine())


def test_arena_cooldown_resets_after_idle():
    _run_cooldown_reset_scenario(ArenaEngine())
