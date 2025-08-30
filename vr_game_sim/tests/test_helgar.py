from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, SkillTriggerType
from vr_game_sim.constants import (
    EFFECT_NAME_JUDGEMENT_MARKER,
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


def test_judgement_mark_multi_trigger_battlefield(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero('Helgar', ['talent_judgement_mark'], [], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    opponents = [
        Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[])
        for i in range(4)
    ]
    sim = GameSimulator(army, opponents[0], mode='battlefield')
    for opp in opponents:
        opp.simulator = sim

    sim._process_skill_triggers(army, opponents[0], SkillTriggerType.ON_COUNTER_ATTACK)
    sim._process_skill_triggers(army, opponents[1], SkillTriggerType.ON_COUNTER_ATTACK)
    sim._process_skill_triggers(army, opponents[2], SkillTriggerType.ON_COUNTER_ATTACK)
    assert army.skill_trigger_counts_this_round.get('talent_judgement_mark') == 3
    sim._process_skill_triggers(army, opponents[3], SkillTriggerType.ON_COUNTER_ATTACK)
    assert army.skill_trigger_counts_this_round.get('talent_judgement_mark') == 3
    sim._process_skill_triggers(army, opponents[0], SkillTriggerType.ON_COUNTER_ATTACK)
    assert army.skill_trigger_counts_this_round.get('talent_judgement_mark') == 3


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
        a.simulator = sim
    class DummyEngine:
        def get_engaged_enemies(self, name):
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
