import random

import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import (
    EffectType,
    SkillTriggerType,
    SkillType,
    PluginSkillLabel,
)


def _make_skill_def() -> dict:
    return {
        "id": "test_skill",
        "name": "Test Skill",
        "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK,
        "labels": [PluginSkillLabel.REACTIVE],
    }


def _make_armies(bonus_stats: dict | None = None) -> tuple[Army, Army, GameSimulator]:
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1200
    dfd_unit.base_def_stat = 600
    attacker = Army(name="A", unit=atk_unit, bonus_stats_config=bonus_stats or {})
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)
    return attacker, defender, sim


def test_reactive_crit_rate_increases_damage():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()
    random.seed(0)
    base_damage, *_ = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    attacker2, defender2, sim2 = _make_armies(
        {"damage_boost": {"reactive_crit_rate": 1.0}}
    )
    random.seed(0)
    crit_damage, *_ = sim2._calculate_generic_skill_damage(
        attacker2,
        defender2,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    assert crit_damage > base_damage
    assert pytest.approx(crit_damage / base_damage, rel=1e-6) == 1.5


def test_gem_evasion_counts_damage_reduction():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()

    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": "Gem Evasion",
        "duration": -1,
        "config": {"evasion_chance": 1.0, "applies_to": ["SKILL"]},
    }
    effect = defender._create_and_add_single_effect(
        effect_data,
        "gem_evasion",
        defender,
        defender,
        attacker,
    )
    assert effect is not None
    defender.activate_queued_effects()

    random.seed(0)
    damage, absorbed, kills, raw = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    assert damage == pytest.approx(0.0)
    assert defender.skill_damage_reduction_totals.get("gem_evasion", 0.0) > 0.0


def test_gem_retribution_counts_kills():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()

    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": "Gem Retribution",
        "duration": -1,
        "config": {"retribution_rate": 1.0},
    }
    effect = defender._create_and_add_single_effect(
        effect_data,
        "gem_retribution",
        defender,
        defender,
        attacker,
    )
    assert effect is not None
    defender.activate_queued_effects()

    random.seed(0)
    damage, absorbed, kills, raw = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )
    assert damage > 0

    attacker.commit_pending_healing_and_damage()
    defender.commit_pending_healing_and_damage()

    assert defender.skill_kill_totals.get("gem_retribution", 0.0) > 0.0
