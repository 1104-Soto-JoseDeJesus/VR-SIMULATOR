import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_DELAYED_RAGE_REDUCTION


def test_skill_rage_reduction_totals_tracks_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    defender.current_rage = 200
    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
        "duration": 0,
        "config": {"rage_reduction": 150},
    }
    eff = defender._create_and_add_single_effect(effect_data, "test_rr", attacker, defender)
    defender.active_effects.append(eff)

    defender.apply_start_of_round_rage_deductions()

    assert defender.skill_rage_reduction_totals.get("test_rr", 0) == 150
    assert defender.current_rage == 50
