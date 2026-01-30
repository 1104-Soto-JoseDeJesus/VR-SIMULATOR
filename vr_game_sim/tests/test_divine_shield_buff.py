from vr_game_sim.hero_definition import Hero
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.constants import (
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_DIVINE_SHIELD_IMMUNITY,
    EFFECT_NAME_DIVINE_SHIELD_STRENGTH,
    EFFECT_NAME_SILENCE_DEBUFF,
)
from vr_game_sim.enums import EffectType


def test_divine_shield_passive_buff_applies_once():
    hero = Hero("Tester", [], [], ["plugin_divine_shield"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL["plugin_divine_shield"]

    # Trigger the skill once and activate its effects
    happened, _ = skill_def["logic_handler"](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()
    assert happened

    buffs = [e for e in army.active_effects if e.name == EFFECT_NAME_DIVINE_SHIELD_STRENGTH]
    assert len(buffs) == 1
    assert buffs[0].magnitude == 0.20
    assert buffs[0].duration == -1

    # Trigger again to ensure the passive does not stack
    skill_def["logic_handler"](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()
    buffs = [e for e in army.active_effects if e.name == EFFECT_NAME_DIVINE_SHIELD_STRENGTH]
    assert len(buffs) == 1


def test_immunity_blocks_single_debuff_name():
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    immunity_data = {
        "effect_type": EffectType.IMMUNITY,
        "name": "Single Immunity",
        "immune_to": EFFECT_NAME_DISARM_DEBUFF,
        "duration": 1,
        "activate_next_round": False,
    }
    army._create_and_add_single_effect(immunity_data, "immune_skill", army, army, enemy)
    army.activate_queued_effects()

    disarm_data = {
        "effect_type": EffectType.DEBUFF,
        "name": EFFECT_NAME_DISARM_DEBUFF,
        "duration": 1,
        "activate_next_round": False,
    }
    created = enemy._create_and_add_single_effect(disarm_data, "debuff_skill", enemy, army, None)
    assert created is None


def test_immunity_blocks_debuffs_from_list():
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    immune_list = [
        EFFECT_NAME_DISARM_DEBUFF,
        EFFECT_NAME_BROKEN_BLADE_DEBUFF,
        EFFECT_NAME_SILENCE_DEBUFF,
    ]
    immunity_data = {
        "effect_type": EffectType.IMMUNITY,
        "name": "List Immunity",
        "immune_to": immune_list,
        "duration": 1,
        "activate_next_round": False,
    }
    army._create_and_add_single_effect(immunity_data, "immune_skill", army, army, enemy)
    army.activate_queued_effects()

    for debuff_name in immune_list:
        debuff_data = {
            "effect_type": EffectType.DEBUFF,
            "name": debuff_name,
            "duration": 1,
            "activate_next_round": False,
        }
        created = enemy._create_and_add_single_effect(debuff_data, "debuff_skill", enemy, army, None)
        assert created is None


def test_divine_shield_immunity_blocks_debuffs_next_round(monkeypatch):
    hero = Hero("Tester", [], [], ["plugin_divine_shield"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL["plugin_divine_shield"]

    army.started_round_with_active_shield = True
    monkeypatch.setattr("vr_game_sim.skill_logic.plugin_skill_handlers.random.random", lambda: 0.0)
    happened, _ = skill_def["logic_handler"](army, enemy, skill_def, None, sim)
    assert happened
    assert any(
        e.name == EFFECT_NAME_DIVINE_SHIELD_IMMUNITY for e in army.effects_to_activate_next_round
    )

    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    assert any(e.name == EFFECT_NAME_DIVINE_SHIELD_IMMUNITY for e in army.active_effects)

    for debuff_name in [
        EFFECT_NAME_DISARM_DEBUFF,
        EFFECT_NAME_BROKEN_BLADE_DEBUFF,
        EFFECT_NAME_SILENCE_DEBUFF,
    ]:
        debuff_data = {
            "effect_type": EffectType.DEBUFF,
            "name": debuff_name,
            "duration": 1,
            "activate_next_round": False,
        }
        created = enemy._create_and_add_single_effect(debuff_data, "debuff_skill", enemy, army, None)
        assert created is None
