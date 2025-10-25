import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType, StatType


def test_damage_boost_tracks_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 1
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    effect_data = {
        "name": "Test Boost",
        "effect_type": EffectType.STAT_MOD,
        "config": {"stat_to_mod": StatType.BASIC_DAMAGE_ADJUST},
        "magnitude": 1.0,
    }
    eff = attacker._create_and_add_single_effect(effect_data, "boost_skill", attacker, attacker)
    attacker.active_effects.append(eff)

    sim._calculate_and_log_attack(attacker, defender, is_counter=False)

    assert attacker.skill_kill_boost_totals.get("boost_skill", 0) > 0


def test_damage_taken_debuff_tracks_basic_attack_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 1
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    effect_data = {
        "name": "Expose",
        "effect_type": EffectType.STAT_MOD,
        "config": {"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
        "magnitude": 0.5,
    }
    eff = defender._create_and_add_single_effect(effect_data, "debuff_skill", attacker, defender)
    defender.active_effects.append(eff)

    sim._calculate_and_log_attack(attacker, defender, is_counter=False)

    assert attacker.skill_kill_boost_totals.get("debuff_skill", 0) > 0


def test_damage_taken_debuff_tracks_skill_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 1
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    effect_data = {
        "name": "Expose",
        "effect_type": EffectType.STAT_MOD,
        "config": {"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
        "magnitude": 0.5,
    }
    eff = defender._create_and_add_single_effect(effect_data, "skill_debuff", attacker, defender)
    defender.active_effects.append(eff)

    sim._calculate_generic_skill_damage(attacker, defender, damage_factor=200)

    assert attacker.skill_kill_boost_totals.get("skill_debuff", 0) > 0


def test_rage_boost_tracks_amount():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="A", unit=unit)
    effect_data = {
        "name": "Rage Boost",
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "config": {"rage_bonus_pct": 0.5},
        "magnitude": 0,
        "duration": 1,
    }
    eff = army._create_and_add_single_effect(effect_data, "boost_rage", army, army)
    army.active_effects.append(eff)

    gained = army.add_rage(100, "base_rage")
    assert gained >= 150
    assert army.skill_rage_boost_totals.get("boost_rage", 0) == pytest.approx(gained - 100)
