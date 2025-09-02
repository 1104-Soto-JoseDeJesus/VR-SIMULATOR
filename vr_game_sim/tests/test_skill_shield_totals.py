import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.enums import EffectType


def test_skill_shield_totals_tracks_units():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="A", unit=unit)
    effect_data = {
        "name": "Test Shield",
        "effect_type": EffectType.SHIELD,
        "magnitude": unit.base_hp_stat,
    }
    army._create_and_add_single_effect(effect_data, "test_shield", army, army)
    assert pytest.approx(army.skill_shield_totals["test_shield"], rel=1e-5) == 1.0

