from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, StatType
from vr_game_sim.constants import EFFECT_NAME_DISARM_DEBUFF


def make_unit(u_type: str) -> Unit:
    return Unit(u_type, 5, initial_count=100)


def test_advantage_adjust_advantage():
    assert GameSimulator.advantage_adjust(make_unit("archers"), make_unit("pikemen")) == 1.05


def test_advantage_adjust_disadvantage():
    assert GameSimulator.advantage_adjust(make_unit("pikemen"), make_unit("archers")) == 0.95


def test_advantage_adjust_neutral():
    assert GameSimulator.advantage_adjust(make_unit("infantry"), make_unit("infantry")) == 1.0


def test_stat_mod_description():
    eff = EffectInstance("s1", EffectType.STAT_MOD, 1, 0.1, {"stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER})
    assert eff.get_functionality_description() == "+10% to Base Attack Multiplier"


def test_shield_description():
    eff = EffectInstance("s1", EffectType.SHIELD, 1, 100)
    assert eff.get_functionality_description() == "Absorbs 100 HP damage"


def test_debuff_description():
    eff = EffectInstance("s1", EffectType.DEBUFF, 1, name=EFFECT_NAME_DISARM_DEBUFF)
    assert eff.get_functionality_description() == "Cannot launch basic attacks"
