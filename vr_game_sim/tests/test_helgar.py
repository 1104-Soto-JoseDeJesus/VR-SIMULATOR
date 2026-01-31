from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, SkillTriggerType
from vr_game_sim.constants import (
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
    EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
)
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_logic.rage_skill_handlers import handle_rage_ruling_trial
import random

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

    happened, logs = skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    remaining_markers = [e for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER]
    pending_markers = [e for e in army.effects_to_activate_next_round if e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS]
    pending_counter_buff = [
        e for e in army.effects_to_activate_next_round if e.name == EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF
    ]

    assert happened
    assert len(remaining_markers) == 0
    assert any("Deals damage" in log[0] for log in logs)
    assert enemy.pending_hp_damage_this_round > 0
    assert pending_markers
    assert pending_counter_buff
    assert not any(e.name == EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF for e in army.active_effects)


def test_judgements_fury_above_threshold_removes_all_markers():
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
    for _ in range(skill_def['config']['marker_threshold'] + 5):
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

    # The skill should queue a marker even below the damage threshold.
    assert happened
    assert logs == []
    assert enemy.pending_hp_damage_this_round == 0
    assert any(
        e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS
        for e in army.effects_to_activate_next_round
    )
    assert not any(
        e.name == EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF
        for e in army.effects_to_activate_next_round
    )


def test_judgements_fury_pending_markers_do_not_count_toward_threshold():
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
    for _ in range(skill_def['config']['marker_threshold'] - 1):
        army._create_and_add_single_effect(marker_data, 'dummy', army, army)
        army.activate_queued_effects()
    pending_marker_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
        "duration": 0,
        "config": {"marker_count": 1},
        "activate_next_round": True,
    }
    army._create_and_add_single_effect(pending_marker_data, 'dummy', army, army)

    happened, logs = skill_def['logic_handler'](army, enemy, skill_def, None, sim)

    assert happened
    assert logs == []
    assert enemy.pending_hp_damage_this_round == 0
    assert sum(1 for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER) == (
        skill_def['config']['marker_threshold'] - 1
    )
    assert not any(
        e.name == EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF
        for e in army.effects_to_activate_next_round
    )


def test_judgements_fury_removes_only_active_markers_on_trigger():
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
    pending_marker_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
        "duration": 0,
        "config": {"marker_count": 1},
        "activate_next_round": True,
    }
    army._create_and_add_single_effect(pending_marker_data, 'dummy', army, army)

    happened, logs = skill_def['logic_handler'](army, enemy, skill_def, None, sim)

    assert happened
    assert any("Deals damage" in log[0] for log in logs)
    assert enemy.pending_hp_damage_this_round > 0
    assert not any(e.name == EFFECT_NAME_JUDGEMENT_MARKER for e in army.active_effects)
    assert any(
        e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS
        for e in army.effects_to_activate_next_round
    )


def test_judgements_fury_queues_marker_for_next_round():
    hero = Hero('Helgar', [], ['base_skill_judgements_fury'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_judgements_fury']

    skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    # Marker should be pending for next round
    assert not any(e.name == EFFECT_NAME_JUDGEMENT_MARKER for e in army.active_effects)
    assert any(e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS for e in army.effects_to_activate_next_round)

    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    army.process_periodic_effects('start_of_round', opponent=enemy)
    army.activate_queued_effects()
    assert sum(1 for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER) == 1


def test_judgements_fury_only_one_marker_per_round():
    hero = Hero('Helgar', [], ['base_skill_judgements_fury'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)

    # Simulate multiple basic attacks hitting Helgar in the same round.
    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK)
    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK)

    # Only one pending marker should be queued for the next round.
    pending = [e for e in army.effects_to_activate_next_round if e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS]
    assert len(pending) == 1

    # After activation, only one actual marker should be present.
    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    army.process_periodic_effects('start_of_round', opponent=enemy)
    army.activate_queued_effects()
    markers = [e for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER]
    assert len(markers) == 1

def test_war_blessing_queues_marker_for_next_round():
    hero = Hero('Helgar', ['talent_war_blessing'], [], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['talent_war_blessing']

    skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    assert not any(e.name == EFFECT_NAME_JUDGEMENT_MARKER for e in army.active_effects)
    assert any(e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS for e in army.effects_to_activate_next_round)

    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    army.process_periodic_effects('start_of_round', opponent=enemy)
    army.activate_queued_effects()
    assert sum(1 for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER) == 1


def test_judgement_mark_queues_markers_for_next_round():
    hero = Hero('Helgar', ['talent_judgement_mark'], [], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['talent_judgement_mark']

    skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    assert not any(e.name == EFFECT_NAME_JUDGEMENT_MARKER for e in army.active_effects)
    assert any(e.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS for e in army.effects_to_activate_next_round)

    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    army.process_periodic_effects('start_of_round', opponent=enemy)
    army.activate_queued_effects()
    assert sum(1 for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER) == 3


def test_judgement_mark_only_once_battlefield(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero('Helgar', ['talent_judgement_mark'], [], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    opponents = [
        Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[])
        for i in range(3)
    ]
    sim = GameSimulator(army, opponents[0], mode='battlefield')
    for opp in opponents:
        opp.register_simulator(sim)

    sim._process_skill_triggers(army, opponents[0], SkillTriggerType.ON_COUNTER_ATTACK)
    sim._process_skill_triggers(army, opponents[1], SkillTriggerType.ON_COUNTER_ATTACK)
    sim._process_skill_triggers(army, opponents[2], SkillTriggerType.ON_COUNTER_ATTACK)
    assert army.triggered_skills_this_round.count('talent_judgement_mark') == 1
    sim._process_skill_triggers(army, opponents[0], SkillTriggerType.ON_COUNTER_ATTACK)
    assert army.triggered_skills_this_round.count('talent_judgement_mark') == 1


def test_ruling_trial_extra_damage_uses_own_markers(monkeypatch):
    hero = Hero('Helgar', [], ['rage_skill_ruling_trial'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['rage_skill_ruling_trial']
    marker = {"effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_JUDGEMENT_MARKER, "duration": -1}
    for _ in range(6):
        army._create_and_add_single_effect(marker, 'm', army, army)
    army.activate_queued_effects()
    happened, logs, _ = handle_rage_ruling_trial(army, enemy, skill_def, {}, sim)
    assert any('extra damage' in log[0] for log in logs)
    army.active_effects.clear()
    enemy.active_effects.clear()
    for _ in range(6):
        enemy._create_and_add_single_effect(marker, 'm', enemy, enemy)
    enemy.activate_queued_effects()
    happened, logs, _ = handle_rage_ruling_trial(army, enemy, skill_def, {}, sim)
    assert not any('extra damage' in log[0] for log in logs)


def test_ruling_trial_hits_indirect_targets_battlefield(monkeypatch):
    hero = Hero('Helgar', [], ['rage_skill_ruling_trial'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[]) for i in range(2, 6)]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def get_engaged_enemies(self, name):
            return [direct] + extras

        def get_direct_attackers(self, name):
            return [direct] + extras
    sim.parent_engine = DummyEngine()
    monkeypatch.setattr(random, 'sample', lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL['rage_skill_ruling_trial']
    handle_rage_ruling_trial(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
    assert extras[2].pending_hp_damage_this_round > 0
    assert extras[3].pending_hp_damage_this_round == 0
