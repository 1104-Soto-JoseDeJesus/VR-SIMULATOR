from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType, StatType
from vr_game_sim.skill_logic.talent_handlers import _schedule_shield_strip


def _make_armies() -> tuple[Army, Army, GameSimulator]:
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1200
    dfd_unit.base_def_stat = 600
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)
    return attacker, defender, sim


def test_mount_shield_strip_removes_only_active_shields():
    attacker, defender, _sim = _make_armies()

    active_shield = defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.SHIELD,
            "name": "Active Shield",
            "duration": 1,
            "shield_factor": 200.0,
            "activate_next_round": True,
        },
        "shield_skill",
        attacker,
        defender,
        attacker,
    )
    assert active_shield in defender.effects_to_activate_next_round
    defender.effects_to_activate_next_round.remove(active_shield)
    active_shield.applied_this_round = False
    defender.active_effects.append(active_shield)

    queued_shield = defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.SHIELD,
            "name": "Queued Shield",
            "duration": 1,
            "shield_factor": 200.0,
            "activate_next_round": True,
        },
        "queued_shield_skill",
        attacker,
        defender,
        attacker,
    )
    assert queued_shield in defender.effects_to_activate_next_round

    buff = defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.STAT_MOD,
            "name": "Non Shield Buff",
            "stat_to_mod": StatType.GENERAL_DAMAGE_MODIFIER,
            "magnitude": 0.1,
            "duration": 1,
            "activate_next_round": False,
        },
        "buff_skill",
        defender,
        defender,
        attacker,
    )
    assert buff in defender.upcoming_effects

    skill_def = {"id": "mount_strip_skill", "name": "Mount Strip"}
    stripped, _log = _schedule_shield_strip(
        attacker,
        defender,
        skill_def,
        "PENDING_MOUNT_SHIELD_STRIP",
    )
    assert stripped
    pending_strip = next(
        eff
        for eff in defender.effects_to_activate_next_round
        if eff.name == "PENDING_MOUNT_SHIELD_STRIP"
    )
    defender.effects_to_activate_next_round.remove(pending_strip)
    defender.upcoming_effects.append(pending_strip)

    defender.activate_queued_effects()
    defender.process_periodic_effects("start_of_round", opponent=attacker)

    assert active_shield not in defender.active_effects
    assert any(e.name == "Non Shield Buff" for e in defender.active_effects)
    assert queued_shield in defender.effects_to_activate_next_round
