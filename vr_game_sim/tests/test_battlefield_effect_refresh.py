import copy
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.hero_definition import Hero
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.skill_definitions import (
    SKILL_REGISTRY_GLOBAL,
    EFFECT_NAME_FATAL_BLEEDING_DOT,
)


def test_fatal_bleeding_waits_and_refreshes():
    engine = BattlefieldEngine()
    original = copy.deepcopy(SKILL_REGISTRY_GLOBAL["talent_fatal_bleeding"])
    modified = copy.deepcopy(original)
    modified["config"]["trigger_interval"] = 1
    modified["config"]["bleed_duration"] = 2
    SKILL_REGISTRY_GLOBAL["talent_fatal_bleeding"] = modified
    try:
        hero = Hero("Bleeder", ["talent_fatal_bleeding"], [], [], SKILL_REGISTRY_GLOBAL)
        atk = Army("A", Unit("pikemen", 5, initial_count=1000), heroes=[hero])
        dfd = Army("B", Unit("pikemen", 5, initial_count=1000))
        engine.add_army(atk, "red")
        engine.add_army(dfd, "blue")
        engine.engage("A", "B")

        engine.tick(1.0)  # Round 1: effect queued for next round
        assert all(e.name != EFFECT_NAME_FATAL_BLEEDING_DOT for e in dfd.active_effects)

        engine.tick(1.0)  # Round 2: first application active, second queued
        bleed = [e for e in dfd.active_effects if e.name == EFFECT_NAME_FATAL_BLEEDING_DOT]
        assert len(bleed) == 1 and bleed[0].duration == 2

        engine.tick(1.0)  # Round 3: reapplication should refresh duration
        bleed = [e for e in dfd.active_effects if e.name == EFFECT_NAME_FATAL_BLEEDING_DOT]
        assert len(bleed) == 1 and bleed[0].duration == 2
    finally:
        SKILL_REGISTRY_GLOBAL["talent_fatal_bleeding"] = original
