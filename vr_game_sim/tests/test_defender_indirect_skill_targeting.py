import uuid

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType, SkillType, EffectType
from vr_game_sim.skill_logic.utility_skill_handlers import handle_generic_single_damage_skill
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.constants import EFFECT_NAME_BROKEN_BLADE_DEBUFF
from vr_game_sim.battlefield_engine import BattlefieldEngine


# Helper to create simple hero with specified skills

def create_hero_with_skills(talent_ids=None, base_skill_ids=None):
    talent_ids = talent_ids or ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"]
    base_skill_ids = base_skill_ids or []
    return Hero("TestHero", talent_ids, base_skill_ids, [], SKILL_REGISTRY_GLOBAL)


# Apply broken blade debuff to prevent counterattacks

def apply_broken_blade(army):
    army.active_effects.append(
        EffectInstance(uuid.uuid4(), "test", EffectType.DEBUFF, duration=1, magnitude=0,
                       name=EFFECT_NAME_BROKEN_BLADE_DEBUFF)
    )


def setup_battlefield(defender):
    atk1 = Army("A1", Unit("pikemen", 5, initial_count=1000))
    atk2 = Army("A2", Unit("pikemen", 5, initial_count=1000))
    engine = BattlefieldEngine()
    engine.add_army(atk1, "red", position=(3, 0), speed=0)
    engine.add_army(atk2, "red", position=(7, 0), speed=0)
    engine.add_army(defender, "blue", position=(5, 0), speed=0)
    engine.engage("A1", defender.name)
    engine.engage("A2", defender.name)
    return engine, atk1, atk2


def test_defender_rage_skill_does_not_hit_indirect_attacker():
    hero = create_hero_with_skills(base_skill_ids=["base_skill_vanquishing_blade"])
    defender = Army("Def", Unit("pikemen", 5, initial_count=1000), heroes=[hero])
    defender.current_rage = 1000
    apply_broken_blade(defender)
    engine, atk1, atk2 = setup_battlefield(defender)
    engine.tick(1.0)  # round 1 – schedule rage skill
    engine.tick(1.0)  # round 2 – execute rage skill
    assert atk1.current_troop_count < atk1.unit.initial_count
    assert atk2.current_troop_count == atk2.unit.initial_count


def test_defender_non_reactive_skill_does_not_hit_indirect_attacker():
    dummy_skill = {
        "id": "test_chance_damage",
        "name": "Test Chance Damage",
        "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND,
        "trigger_chance": 1.0,
        "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "config": {"damage_factor": 1000.0},
    }
    SKILL_REGISTRY_GLOBAL[dummy_skill["id"]] = dummy_skill
    try:
        hero = create_hero_with_skills(talent_ids=[dummy_skill["id"], "dummy_talent_empty", "dummy_talent_empty"])
        defender = Army("Def2", Unit("pikemen", 5, initial_count=1000), heroes=[hero])
        apply_broken_blade(defender)
        engine, atk1, atk2 = setup_battlefield(defender)
        engine.tick(1.0)
        assert atk1.current_troop_count < atk1.unit.initial_count
        assert atk2.current_troop_count == atk2.unit.initial_count
    finally:
        SKILL_REGISTRY_GLOBAL.pop(dummy_skill["id"], None)
