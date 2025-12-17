import uuid

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
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
    eff = EffectInstance(uuid.uuid4(), "s1", EffectType.STAT_MOD, 1, 0.1, {"stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER})
    assert eff.get_functionality_description() == "+10% to Base Attack Multiplier"


def test_shield_description():
    eff = EffectInstance(uuid.uuid4(), "s1", EffectType.SHIELD, 1, 100)
    assert eff.get_functionality_description() == "Absorbs 100 HP damage"


def test_debuff_description():
    eff = EffectInstance(uuid.uuid4(), "s1", EffectType.DEBUFF, 1, name=EFFECT_NAME_DISARM_DEBUFF)
    assert eff.get_functionality_description() == "Cannot launch basic attacks"


def test_resolve_advantage_additive_and_off_modes():
    attacker_army = Army("att", make_unit("archers"))
    defender_army = Army("def", make_unit("pikemen"))

    additive_sim = GameSimulator(attacker_army, defender_army, advantage_mode="additive")
    adv_multiplier, adv_bonus = additive_sim._resolve_advantage_adjustment(
        attacker_army.unit, defender_army.unit
    )
    assert adv_multiplier == 1.0
    assert adv_bonus == 0.05

    off_sim = GameSimulator(
        Army("att_off", make_unit("archers")), Army("def_off", make_unit("pikemen")), advantage_mode="off"
    )
    adv_multiplier_off, adv_bonus_off = off_sim._resolve_advantage_adjustment(
        off_sim.army1.unit, off_sim.army2.unit
    )
    assert adv_multiplier_off == 1.0
    assert adv_bonus_off == 0.0
