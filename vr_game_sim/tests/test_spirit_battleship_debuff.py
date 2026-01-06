import uuid

import pytest

from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, StatType
from vr_game_sim.unit_definition import Unit


def test_debuff_stat_modifiers_apply_to_defense():
    unit = Unit(unit_type="infantry", tier=4, initial_count=100)
    base_defense = unit.effective_defense([])
    assert base_defense == pytest.approx(157)

    defense_reduction = EffectInstance(
        uuid.uuid4(),
        "rage_skill_spirit_battleship",
        EffectType.DEBUFF,
        duration=1,
        magnitude=-0.30,
        config={"stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER},
    )

    effective_defense = unit.effective_defense([defense_reduction])
    assert effective_defense == pytest.approx(109.9, rel=1e-3)
    assert defense_reduction.is_harmful_for_target()
