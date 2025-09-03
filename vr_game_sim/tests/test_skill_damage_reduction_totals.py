import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType, StatType


def test_skill_damage_reduction_totals_tracks_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 1
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    effect_data = {
        "name": "Test DR",
        "effect_type": EffectType.STAT_MOD,
        "config": {"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
        "magnitude": -0.5,
    }
    eff = defender._create_and_add_single_effect(effect_data, "test_dr", defender, defender)
    defender.active_effects.append(eff)

    sim._calculate_and_log_attack(attacker, defender, is_counter=False)

    assert defender.skill_damage_reduction_totals.get("test_dr", 0) > 0
