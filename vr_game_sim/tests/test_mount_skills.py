import copy
import os

import pytest

try:
    from PyQt6 import QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtWidgets = None  # type: ignore[assignment]

try:
    from vr_game_sim.gui_main import ArmyFrame
except ImportError:  # pragma: no cover - optional dependency
    ArmyFrame = None  # type: ignore[assignment]

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import EffectType, SkillTriggerType, StatType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.unit_definition import Unit
from vr_game_sim.main import create_armies_from_data


def _create_army(name: str) -> Army:
    unit = Unit(unit_type="infantry", tier=7, initial_count=100000)
    return Army(name=name, unit=unit)


def _get_app():
    if QtWidgets is None:
        pytest.skip("PyQt6 is required for this test")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _prepare_for_trigger(army: Army, opponent: Army) -> None:
    army.skill_last_triggered_round.clear()
    army.skill_trigger_counts_this_round.clear()
    army.triggered_skills_this_round.clear()
    army.skill_trigger_counts.clear()
    opponent.skill_trigger_counts.clear()
    army.army_round = 1
    opponent.army_round = 1
    opponent.pending_hp_damage_this_round = 0.0
    army.pending_hp_damage_this_round = 0.0
    army.rage_added_this_round = 0.0
    opponent.rage_added_this_round = 0.0
    army.current_rage = 0.0
    opponent.current_rage = 0.0
    army.mount_rage_grants_this_round.clear()
    opponent.mount_rage_grants_this_round.clear()


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


def test_mount_passive_applied_once():
    army = _create_army("Sigma")
    opponent = _create_army("Tau")
    army.set_mount_skills({"slot1_primary": ["mount_command_crippling_strike"]})
    simulator = GameSimulator(army, opponent, track_stats=False)

    _prepare_for_trigger(army, opponent)

    for _ in range(2):
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
        army.triggered_skills_this_round.clear()
        army.skill_trigger_counts_this_round.clear()

    passive_effects = [
        eff
        for eff in army.active_effects
        if eff.effect_type == EffectType.STAT_MOD
        and eff.config.get("mount_metadata", {}).get("stat_key")
        == StatType.COMMAND_SKILL_CRIT_RATE.value
    ]

    assert len(passive_effects) == 1
    assert passive_effects[0].magnitude == pytest.approx(0.02)


def test_duplicate_mount_skill_instances_trigger_per_slot():
    army = _create_army("Omega")
    opponent = _create_army("Kappa")
    army.set_mount_skills(
        {
            "hero1_slot1": "mount_command_crippling_strike",
            "hero2_slot1": "mount_command_crippling_strike",
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

    assert army.skill_trigger_counts.get("mount_command_crippling_strike") == 2
    assert {
        key for key in army.triggered_skills_this_round if "mount_command_crippling_strike" in key
    } == {
        "mount_command_crippling_strike|hero1_slot1",
        "mount_command_crippling_strike|hero2_slot1",
    }


def test_mount_buff_dedup_across_heroes():
    army = _create_army("Iota")
    opponent = _create_army("Theta")
    army.set_mount_skills(
        {
            "hero1_slot2": "mount_command_lava_beast",
            "hero2_slot2": "mount_command_ravens_breath",
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
    meta = relevant_effects[0].config.get("mount_metadata", {})
    assert meta.get("slot") == 2


def test_mount_rage_gain_deduplicated():
    army = _create_army("Lambda")
    opponent = _create_army("Mu")
    army.set_mount_skills(
        {
            "hero1_slot1": "mount_command_untamed_wilderness",
            "hero2_slot1": "mount_command_untamed_wilderness",
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

    assert army.skill_trigger_counts.get("mount_command_untamed_wilderness") == 2
    assert army.rage_added_this_round == pytest.approx(40.0)
    assert army.current_rage == pytest.approx(40.0)


@pytest.mark.skipif(QtWidgets is None or ArmyFrame is None, reason="PyQt6 not available")
def test_mount_skills_round_trip_ui():
    _get_app()
    frame = ArmyFrame(1)
    frame.unit_combo.setCurrentText("archers")
    hero_name = next(name for name in frame.hero_options if name not in {"None", "Custom"})
    frame.hero1_combo.setCurrentText(hero_name)
    frame._set_mount_loadout(
        1,
        {"1": "mount_command_crippling_strike"},
        {"1": {"config": {"interval_seconds": 9}}},
    )
    frame._update_mount_skills_button()

    cfg = frame.build_config()
    assert cfg["heroes"][0]["mount_skill_ids"] == {"1": "mount_command_crippling_strike"}
    assert cfg["heroes"][0]["mount_skill_overrides"]["1"]["config"]["interval_seconds"] == 9

    frame2 = ArmyFrame(1)
    frame2.populate_from_config(cfg)
    rebuilt = frame2.build_config()
    assert rebuilt["heroes"][0]["mount_skill_ids"] == cfg["heroes"][0]["mount_skill_ids"]
    assert (
        rebuilt["heroes"][0]["mount_skill_overrides"]["1"]["config"]["interval_seconds"]
        == 9
    )
    assert frame2.mount_skills_btn.text() == "Mount Skills (1)"
    assert "Crippling" in frame2.mount_skills_btn.toolTip()


def test_mount_skills_survive_create_armies_round_trip():
    setup_payload = [
        {
            "army_name": "Alpha",
            "unit_type": "archers",
            "tier": 7,
            "count": 100000,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "unrevivable_ratio": 0.65,
            "heroes": [
                {
                    "hero_name_or_preset": "CustomHero",
                    "talent_ids": ["dummy_talent_empty"] * 3,
                    "base_skill_ids": [],
                    "plugin_skill_ids": [],
                    "mount_skill_ids": {"1": "mount_command_crippling_strike"},
                    "mount_skill_overrides": {"1": {"config": {"interval_seconds": 9}}},
                }
            ],
        },
        {
            "army_name": "Beta",
            "unit_type": "infantry",
            "tier": 7,
            "count": 100000,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "unrevivable_ratio": 0.65,
            "heroes": [],
        },
    ]

    armies = create_armies_from_data(copy.deepcopy(setup_payload))
    mount_ids = armies[0].mount_skill_ids
    assert mount_ids == {"hero1_slot1": ["mount_command_crippling_strike"]}
    assert any(
        skill.get("id") == "mount_command_crippling_strike"
        and skill.get("config", {}).get("interval_seconds") == 9
        for skill in armies[0].mount_skills
    )
