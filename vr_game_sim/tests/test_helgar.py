from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import (
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
)
from vr_game_sim.game_simulator import GameSimulator

def test_helgar_preset_loading():
    preset = HERO_PRESETS.get('helgar')
    assert preset is not None
    hero = Hero('Helgar', preset['talents'], preset['base_skills'], preset['plugin_skills'], SKILL_REGISTRY_GLOBAL)
    assert len(hero.skills) == 5  # 3 talents + 2 base skills


def test_judgement_marker_stacks():
    hero = Hero('Helgar', [], [], [], SKILL_REGISTRY_GLOBAL)
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    marker_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_JUDGEMENT_MARKER,
        "duration": -1,
    }
    for _ in range(3):
        army._create_and_add_single_effect(marker_data, 'test_skill', army, army)
        army.activate_queued_effects()
    markers = [e for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER]
    assert len(markers) == 3


def test_judgements_fury_triggers_at_threshold():
    hero = Hero('Helgar', [], ['base_skill_judgements_fury'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_judgements_fury']

    marker_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_JUDGEMENT_MARKER,
        "duration": -1,
    }
    for _ in range(skill_def['config']['marker_threshold']):
        army._create_and_add_single_effect(marker_data, 'dummy', army, army)
        army.activate_queued_effects()

    happened, _ = skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    remaining_markers = [e for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER]

    assert happened
    assert len(remaining_markers) == 0


def test_judgements_fury_below_threshold_no_buff():
    hero = Hero('Helgar', [], ['base_skill_judgements_fury'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_judgements_fury']

    happened, logs = skill_def['logic_handler'](army, enemy, skill_def, None, sim)

    assert not happened
    assert logs == []


def test_saintly_guardian_in_active_effects():
    hero = Hero('Helgar', HERO_PRESETS['helgar']['talents'], HERO_PRESETS['helgar']['base_skills'], HERO_PRESETS['helgar']['plugin_skills'], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    lines = sim._log_active_effects_for_report()
    assert any(EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST in line for line in lines)
