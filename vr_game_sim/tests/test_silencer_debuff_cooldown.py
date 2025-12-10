import copy

from vr_game_sim.hero_definition import Hero
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType, EffectType
from vr_game_sim.constants import (
    EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
)


def _make_army_with_skill(skill_def):
    hero = Hero("H", [], [], [skill_def["id"]], SKILL_REGISTRY_GLOBAL)
    return Army("Army", Unit("pikemen", 5, initial_count=10), heroes=[hero])


def test_silencer_triggers_on_basic_attack_and_respects_existing_silence():
    silencer_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["plugin_silencer"])
    silencer_def["id"] = "plugin_silencer_test"
    silencer_def["trigger_chance"] = 1.0
    SKILL_REGISTRY_GLOBAL["plugin_silencer_test"] = silencer_def

    army1 = _make_army_with_skill(silencer_def)
    army2 = Army("B", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    sim.round = 1

    sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)
    assert any(
        eff.name == EFFECT_NAME_SILENCE_DEBUFF for eff in army2.effects_to_activate_next_round
    )

    if army2.effects_to_activate_next_round:
        army2.upcoming_effects.extend(army2.effects_to_activate_next_round)
        army2.effects_to_activate_next_round.clear()
    army2.activate_queued_effects()
    army1.triggered_skills_this_round.clear()
    army1.skill_trigger_counts_this_round.clear()
    army1.skill_triggers_against_this_round.clear()
    sim.round = 2
    army2.pending_hp_damage_this_round = 0
    sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)
    assert army2.pending_hp_damage_this_round > 0
    assert (
        sum(1 for e in army2.active_effects if e.name == EFFECT_NAME_SILENCE_DEBUFF) == 1
    )

    del SKILL_REGISTRY_GLOBAL["plugin_silencer_test"]


def test_debuffs_have_two_round_cooldown():
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    effect_names = [
        EFFECT_NAME_SILENCE_DEBUFF,
        EFFECT_NAME_DISARM_DEBUFF,
        EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    ]
    army2.is_rally = True

    for name in effect_names:
        data = {
            "effect_type": EffectType.DEBUFF,
            "name": name,
            "duration": 1,
            "activate_next_round": True,
        }
        sim.round = 1
        first = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
        assert first
        second = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
        assert second is None
        sim.round = 2
        third = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
        assert third is None
        sim.round = 3
        fourth = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
        assert fourth
        army2.active_effects.clear()
        army2.upcoming_effects.clear()
        army2.effects_to_activate_next_round.clear()
        army2.debuff_last_applied_round.clear()


def test_rally_only_debuff_cooldown(sim, army1, army2):
    """Non-rally armies should not throttle duplicate debuff scheduling."""

    data = {
        "effect_type": EffectType.DEBUFF,
        "name": EFFECT_NAME_SILENCE_DEBUFF,
        "duration": 1,
        "activate_next_round": True,
    }

    sim.round = 5
    first = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
    assert first

    second = army2._create_and_add_single_effect(data, "s", army1, army2, army1)
    assert second
