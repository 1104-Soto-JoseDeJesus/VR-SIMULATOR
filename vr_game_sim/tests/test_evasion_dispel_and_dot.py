import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.constants import (
    EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
    EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
)
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import DoTType, EffectType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.unit_definition import Unit


def _basic_armies():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 100
    attacker = Army(name="Attack", unit=atk_unit)
    defender = Army(name="Defend", unit=dfd_unit)
    simulator = GameSimulator(attacker, defender)
    return attacker, defender, simulator


def test_blessed_negation_dispels_heimdall_evasion():
    attacker, defender, simulator = _basic_armies()

    evasion_effect = defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
            "duration": 1,
            "config": {
                "evasion_chance": 0.25,
                "applies_to": ["BASIC", "COUNTER", "SKILL"],
                "is_dispellable": True,
            },
        },
        "heimdall_evasion",
        defender,
        defender,
        attacker,
    )
    evasion_effect.applied_this_round = False
    defender.active_effects.append(evasion_effect)

    pending_dispel = defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
            "duration": 0,
            "config": {
                "buff_ids_to_remove": [evasion_effect.id],
                "targeted_buff_names_initial_log": [evasion_effect.name],
            },
        },
        "blessed_negation",
        attacker,
        defender,
        attacker,
    )
    pending_dispel.applied_this_round = False
    defender.active_effects.append(pending_dispel)

    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert evasion_effect not in defender.active_effects


def test_dot_damage_bypasses_evasion():
    attacker, defender, simulator = _basic_armies()

    evasion_effect = EffectInstance(
        id=uuid.uuid4(),
        source_skill_id="heimdall_evasion",
        name=EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
        effect_type=EffectType.CUSTOM_SKILL_EFFECT,
        duration=1,
        magnitude=0.0,
        config={
            "evasion_chance": 1.0,
            "applies_to": ["BASIC", "COUNTER", "SKILL"],
            "is_dispellable": True,
        },
        applied_this_round=False,
    )
    defender.active_effects.append(evasion_effect)

    dot_effect = EffectInstance(
        id=uuid.uuid4(),
        source_skill_id="bleed_test",
        effect_type=EffectType.DAMAGE_OVER_TIME,
        duration=0,
        magnitude=0.0,
        config={
            "dot_type": DoTType.GENERIC,
            "dot_damage_per_round": 200,
            "source_army_name": attacker.name,
        },
        applied_this_round=False,
    )
    defender.active_effects.append(dot_effect)

    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert defender.pending_hp_damage_this_round > 0
