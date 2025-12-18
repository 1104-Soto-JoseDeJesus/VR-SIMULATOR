import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, DoTType, StatType
from vr_game_sim.game_simulator import GameSimulator


def test_chiefs_might_bleed_respects_passive_boosts_with_missing_caster_name():
    attacker = Army("Attacker", Unit("archers", 5, initial_count=100), heroes=[])
    defender = Army("Defender", Unit("pikemen", 5, initial_count=100), heroes=[])

    bleed_bonus = EffectInstance(
        uuid.uuid4(),
        "bleed_bonus",
        EffectType.STAT_MOD,
        -1,
        magnitude=0.25,
        config={"stat_to_mod": StatType.BLEED_DAMAGE_BOOST},
    )
    attacker.active_effects.extend([bleed_bonus, bleed_bonus.__class__(
        uuid.uuid4(), "bleed_bonus_2", EffectType.STAT_MOD, -1, magnitude=0.25,
        config={"stat_to_mod": StatType.BLEED_DAMAGE_BOOST}
    )])

    dot_effect = EffectInstance(
        uuid.uuid4(),
        "chiefs_might_bleed",
        EffectType.DAMAGE_OVER_TIME,
        0,
        config={
            "dot_type": DoTType.BLEED,
            "status_effect_factor": 200.0,
            "snapshotted_attacker_total_attack": 100.0,
            "snapshotted_defender_total_defense": 100.0,
            "snapshotted_attacker_troop_scalar": 1.0,
            "original_caster_army_name": "Unknown Co-Op Caster",
            "original_caster_army_ref": attacker,
            "effect_owner_army_ref": attacker,
            "source_army_name": attacker.name,
        },
        name="Chief's Might Bleed",
        applied_this_round=False,
    )
    defender.active_effects.append(dot_effect)

    GameSimulator(attacker, defender, track_stats=False)

    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert defender.pending_hp_damage_this_round == 1.5
