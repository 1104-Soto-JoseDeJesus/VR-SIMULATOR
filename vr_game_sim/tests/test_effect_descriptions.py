from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, StatType, DoTType
from vr_game_sim.constants import (
    EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_DELAYED_RAGE_GAIN,
)


def test_stat_mod_description():
    eff = EffectInstance("s", EffectType.STAT_MOD, 1, 0.1, {"stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER})
    assert eff.get_functionality_description() == "+10% to Base Attack Multiplier"


def test_shield_description():
    eff = EffectInstance("s", EffectType.SHIELD, 1, 100)
    assert eff.get_functionality_description() == "Absorbs 100 HP damage"


def test_immunity_description():
    eff = EffectInstance("s", EffectType.IMMUNITY, 1, 0, {"immune_to": "Disarm"})
    assert eff.get_functionality_description() == "Immunity to Disarm"


def test_debuff_description():
    eff = EffectInstance("s", EffectType.DEBUFF, 1, name=EFFECT_NAME_SILENCE_DEBUFF)
    assert eff.get_functionality_description() == "Prevents Rage Skill cast"


def test_dot_description():
    eff = EffectInstance("s", EffectType.DAMAGE_OVER_TIME, 1, 0, {"dot_type": DoTType.BURN, "status_effect_factor": 50})
    assert eff.get_functionality_description() == "Burn Damage Over Time (Factor: 50)"


def test_hot_description():
    eff = EffectInstance("s", EffectType.HEAL_OVER_TIME, 2, 5.0)
    assert eff.get_functionality_description() == "Heals over time (Factor: 5)"


def test_custom_effect_description():
    eff = EffectInstance(
        "s",
        EffectType.CUSTOM_SKILL_EFFECT,
        1,
        0,
        {"rage_amount": 5},
        name=EFFECT_NAME_DELAYED_RAGE_GAIN,
    )
    assert eff.get_functionality_description() == "Gain 5 rage next round"
