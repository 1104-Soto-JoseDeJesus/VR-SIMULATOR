import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import SkillTriggerType, StatType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.unit_definition import Unit


def _create_army(name: str) -> Army:
    unit = Unit(unit_type="infantry", tier=7, initial_count=100000)
    return Army(name=name, unit=unit)


def _prepare_for_trigger(army: Army, opponent: Army) -> None:
    army.skill_last_triggered_round.clear()
    army.skill_trigger_counts_this_round.clear()
    army.triggered_skills_this_round.clear()
    army.skill_trigger_counts.clear()
    opponent.skill_trigger_counts.clear()
    army.army_round = 1
    opponent.army_round = 1
    opponent.pending_hp_damage_this_round = 0.0


def test_mount_buff_stacking_keeps_highest_magnitude():
    army = _create_army("Alpha")
    opponent = _create_army("Beta")
    army.set_mount_skills(
        {
            "slot1_primary": [
                "mount_command_bone_spurs",
                "mount_command_ravens_breath",
            ]
        }
    )
    simulator = GameSimulator(army, opponent, track_stats=False)

    _prepare_for_trigger(army, opponent)

    simulator._process_skill_triggers(
        army,
        opponent,
        SkillTriggerType.CHANCE_PER_ROUND,
        event_data={
            "opponent_for_shield_calc": opponent,
            "direct_target_army": opponent,
        },
    )
    army.activate_queued_effects()

    relevant_effects = [
        eff
        for eff in army.active_effects
        if eff.config.get("mount_metadata")
        and eff.config["mount_metadata"].get("stat_key") == StatType.GENERAL_DAMAGE_MODIFIER.value
    ]

    assert len(relevant_effects) == 1
    assert relevant_effects[0].magnitude == pytest.approx(0.25)
    mount_meta = relevant_effects[0].config.get("mount_metadata", {})
    # Slot index should be captured from the slot key so stacking can be evaluated per slot.
    assert mount_meta.get("slot") == 1
    # Target name ensures stacking checks separate allies and enemies.
    assert mount_meta.get("target_name") == army.name


def test_mount_direct_damage_skills_both_trigger():
    army = _create_army("Gamma")
    opponent = _create_army("Delta")
    army.set_mount_skills(
        {
            "slot1_primary": [
                "mount_command_crippling_strike",
                "mount_command_untamed_wilderness",
            ]
        }
    )
    simulator = GameSimulator(army, opponent, track_stats=False)

    _prepare_for_trigger(army, opponent)

    simulator._process_skill_triggers(
        army,
        opponent,
        SkillTriggerType.CHANCE_PER_ROUND,
        event_data={
            "opponent_for_shield_calc": opponent,
            "direct_target_army": opponent,
        },
    )

    expected_ids = {
        "mount_command_crippling_strike",
        "mount_command_untamed_wilderness",
    }
    triggered_ids = {
        sid for sid in expected_ids if army.skill_trigger_counts.get(sid, 0) > 0
    }

    assert triggered_ids == expected_ids
    assert opponent.pending_hp_damage_this_round > 0
