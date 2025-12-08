import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, DoTType, StatType
from vr_game_sim.game_simulator import GameSimulator


def _create_dot_effect(status_factor: float) -> EffectInstance:
    return EffectInstance(
        uuid.uuid4(),
        "dot_skill",
        EffectType.DAMAGE_OVER_TIME,
        0,
        config={
            "dot_type": DoTType.BURN,
            "status_effect_factor": status_factor,
            "snapshotted_attacker_total_attack": 100.0,
            "snapshotted_defender_total_defense": 100.0,
            "snapshotted_attacker_troop_scalar": 1.0,
            "original_caster_army_name": "Attacker",
            "source_army_name": "Attacker",
        },
        name="Test DoT",
        applied_this_round=False,
    )


def test_damage_reduction_affects_dot_by_default():
    attacker = Army("Attacker", Unit("archers", 5, initial_count=100), heroes=[])
    defender = Army("Defender", Unit("pikemen", 5, initial_count=100), heroes=[])
    reduction = EffectInstance(
        uuid.uuid4(),
        "reduction",
        EffectType.STAT_MOD,
        0,
        magnitude=-0.5,
        config={"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
    )
    defender.active_effects.append(reduction)
    defender.active_effects.append(_create_dot_effect(200.0))

    sim = GameSimulator(attacker, defender, track_stats=False)
    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert defender.pending_hp_damage_this_round == 0.5


def test_damage_reduction_toggle_restores_original_behavior():
    attacker = Army("Attacker", Unit("archers", 5, initial_count=100), heroes=[])
    defender = Army("Defender", Unit("pikemen", 5, initial_count=100), heroes=[])
    reduction = EffectInstance(
        uuid.uuid4(),
        "reduction",
        EffectType.STAT_MOD,
        0,
        magnitude=-0.5,
        config={"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
    )
    defender.active_effects.append(reduction)
    defender.active_effects.append(_create_dot_effect(200.0))

    sim = GameSimulator(attacker, defender, track_stats=False, damage_reduction_affects_dots=False)
    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert defender.pending_hp_damage_this_round == 1.0
