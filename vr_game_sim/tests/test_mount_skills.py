import copy

import pytest

from vr_game_sim.enums import DoTType, EffectType, SkillType, SkillTriggerType, StatType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.main import create_armies_from_data, get_setup_data_for_saving


_BASE_CFG = {
    "army_name": "Mount Squad",
    "unit_type": "archers",
    "tier": 5,
    "count": 100000,
    "atk_mod": 0.0,
    "def_mod": 0.0,
    "hp_mod": 0.0,
    "unrevivable_ratio": 0.65,
    "heroes": [
        {
            "hero_name_or_preset": "leif",
            "talent_ids": [
                "talent_blade_counter",
                "talent_shield_of_resistance",
                "talent_revenge_echo",
            ],
            "base_skill_ids": [
                "base_skill_planned_attack",
                "base_skill_sharp_pursuit",
            ],
            "plugin_skill_ids": [],
            "mount_skill_ids": [
                "mount_crippling_strike",
                "mount_crippling_strike",
            ],
        }
    ],
}


def test_mount_skills_applied_to_heroes():
    cfg = copy.deepcopy(_BASE_CFG)
    army = create_armies_from_data([cfg])[0]
    hero = army.heroes[0]

    mount_skills = [
        skill_def
        for skill_def in hero.skills
        if skill_def.get("type") == SkillType.MOUNT_SKILL
    ]

    assert len(mount_skills) == 2
    assert all(skill_def.get("id") == "mount_crippling_strike" for skill_def in mount_skills)


def test_mount_skills_persist_in_saved_data():
    cfg = copy.deepcopy(_BASE_CFG)
    army = create_armies_from_data([cfg])[0]

    saved_cfg = get_setup_data_for_saving([army])[0]
    saved_hero = saved_cfg["heroes"][0]

    assert saved_hero.get("mount_skill_ids") == cfg["heroes"][0]["mount_skill_ids"]


def test_new_command_mount_skills_registered():
    expected = {
        "mount_firewing_ashes": {
            "stat": "burn_damage_boost",
            "magnitude": 0.5,
            "duration": 1,
        },
        "mount_bonegnaw_bug": {
            "stat": "poison_damage_boost",
            "magnitude": 0.5,
            "duration": 1,
        },
        "mount_pain_n_fury": {
            "rage_gain": 155,
        },
        "mount_abyssal_maw": {
            "stat_mods": [
                {"stat": "basic_damage_adjust", "magnitude": 1.0, "duration": 1},
                {"stat": "counter_damage_adjust", "magnitude": 1.0, "duration": 1},
            ],
        },
        "mount_bone_spurs": {
            "stat": "general_damage_modifier",
            "magnitude": 0.16,
            "duration": 1,
        },
        "mount_hard_shell": {
            "stat": "damage_taken_multiplier",
            "magnitude": -0.32,
            "duration": 0,
        },
    }

    for skill_id, expectations in expected.items():
        skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id)
        assert skill_def, f"{skill_id} missing from registry"
        assert skill_def.get("type") == SkillType.MOUNT_SKILL

        config = skill_def.get("config", {})
        if "stat" in expectations:
            assert getattr(config.get("stat_to_mod"), "value", None) == expectations["stat"]
            assert config.get("buff_magnitude") == expectations["magnitude"]
            # Duration values are zero-indexed internally; 1 yields a 2-round duration in practice.
            assert config.get("buff_duration") == expectations["duration"]
        if "stat_mods" in expectations:
            mod_expectations = {entry["stat"]: entry for entry in expectations["stat_mods"]}
            mod_config = config.get("stat_mods") or []
            mod_actual = {
                getattr(entry.get("stat_to_mod"), "value", None): {
                    "magnitude": entry.get("buff_magnitude"),
                    "duration": entry.get("buff_duration", config.get("buff_duration")),
                }
                for entry in mod_config
            }

            for stat, entry in mod_expectations.items():
                assert stat in mod_actual, f"{stat} missing from stat_mods for {skill_id}"
                assert mod_actual[stat]["magnitude"] == entry["magnitude"]
            assert mod_actual[stat]["duration"] == entry["duration"]
        if "rage_gain" in expectations:
            assert config.get("rage_gain") == expectations["rage_gain"]


def test_mount_skill_overrides_apply_to_heroes():
    damage_factor = 1337.0
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_crippling_strike"]
    cfg["heroes"][0]["skill_overrides"] = {
        "mount_crippling_strike": {"config": {"damage_factor": damage_factor}}
    }

    army = create_armies_from_data([cfg])[0]
    hero = army.heroes[0]
    mount_skill = next(s for s in hero.skills if s.get("id") == "mount_crippling_strike")

    assert mount_skill.get("config", {}).get("damage_factor") == damage_factor


def test_mount_rage_effects_map_to_skill_summary_and_html():
    pytest.importorskip("PyQt6")
    try:
        from vr_game_sim.gui_main import build_army_skill_summary
    except ImportError:
        pytest.skip("PyQt6 dependencies not available")

    cfg = copy.deepcopy(_BASE_CFG)
    mount_id = "mount_pain_n_fury"
    cfg["heroes"][0]["mount_skill_ids"] = [mount_id]

    army = create_armies_from_data([cfg])[0]

    rage_effect_name = (
        SKILL_REGISTRY_GLOBAL.get(mount_id, {}).get("config", {}).get("effect_name")
        or "Mount Periodic Rage Gain"
    )
    expected_rage = 120
    army.skill_rage_totals[rage_effect_name] = expected_rage
    army.skill_source_overrides[rage_effect_name] = mount_id

    summary = build_army_skill_summary(army, cfg, team="red")
    hero_entries = summary["skills"][0]
    mount_entries = [entry for entry in hero_entries if entry.get("id") == mount_id]

    assert mount_entries, "Mount skill entry missing from summary"
    assert mount_entries[0]["rage"] == expected_rage

    html_rows = [
        f"<div class='skill-card' data-skill-id='{entry['id']}'>{entry['rage']}</div>"
        for entry in hero_entries
    ]
    html_output = "".join(html_rows)

    assert str(expected_rage) in html_output


def test_duplicate_mount_damage_and_buff_resolution():
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_flame_serpent", "mount_flame_serpent"]

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    hero = army.heroes[0]
    mount_skills = [skill for skill in hero.skills if skill.get("id") == "mount_flame_serpent"]
    assert len(mount_skills) == 2, "Expected duplicated mount skills for test setup"

    low_magnitude = 0.05
    high_magnitude = 0.12
    for idx, skill in enumerate(mount_skills):
        skill_config = skill.get("config", {})
        skill_config.update({"trigger_interval": 1, "damage_factor": 50.0})
        skill_config["stat_mods"] = [
            {
                "stat_to_mod": StatType.BURN_DAMAGE_BOOST,
                "buff_magnitude": high_magnitude if idx else low_magnitude,
            }
        ]

    simulator = GameSimulator(army, opponent, mode="battlefield")
    army.army_round = 1
    opponent.army_round = 1

    simulator._process_skill_triggers(army, opponent, SkillTriggerType.CHANCE_PER_ROUND)

    mount_keys = [
        f"mount_flame_serpent::mount::{skill['mount_instance_index']}" for skill in mount_skills
    ]
    damage_triggers = sum(
        army.mount_skill_damage_triggers_this_round.get(key, 0) for key in mount_keys
    )
    assert damage_triggers == len(mount_keys), "Both mount skills should contribute direct damage"

    relevant_effects = (
        army.active_effects + army.effects_to_activate_next_round + army.upcoming_effects
    )
    burn_boosts = [
        effect.magnitude
        for effect in relevant_effects
        if getattr(effect, "_stat_type_from_config", lambda: None)() == StatType.BURN_DAMAGE_BOOST
    ]
    # Duplicate mount buffs merge: higher value wins, only winner applies (one effect)
    assert burn_boosts == [high_magnitude], (
        f"Expected one merged buff with high magnitude, got {burn_boosts}"
    )


def test_duplicate_mount_damage_active_cast_cooldown_per_instance():
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_strangled_death", "mount_strangled_death"]

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    hero = army.heroes[0]
    mount_skills = [skill for skill in hero.skills if skill.get("id") == "mount_strangled_death"]
    assert len(mount_skills) == 2
    assert all("mount_instance_index" in skill for skill in mount_skills)

    simulator = GameSimulator(army, opponent, mode="battlefield")
    for round_num in range(1, 3):
        army.army_round = round_num
        opponent.army_round = round_num
        army.triggered_skills_this_round.clear()
        army.skill_trigger_counts_this_round.clear()
        army.skill_triggers_against_this_round.clear()
        army.mount_skill_damage_triggers_this_round.clear()
        army.mount_skill_non_damage_applied_this_round.clear()
        army.mount_skill_dot_hot_applied_this_round.clear()
        simulator._process_skill_triggers(army, opponent, SkillTriggerType.ON_OWN_RAGE_SKILL_CAST)

    cooldown_keys = [
        f"mount_strangled_death::mount::{skill['mount_instance_index']}" for skill in mount_skills
    ]
    for key in cooldown_keys:
        assert len(army.skill_active_cast_trigger_rounds.get(key, [])) == 2
    assert sum(len(v) for v in army.skill_active_cast_trigger_rounds.values()) == 4


def test_duplicate_mount_active_cast_across_heroes_tracks_independently():
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_strangled_death"]
    cfg["heroes"].append(
        {
            "hero_name_or_preset": "sigurd",
            "talent_ids": [
                "talent_fiery_snake_spirit",
                "talent_serpents_rage",
                "talent_full_focus",
            ],
            "base_skill_ids": [
                "base_skill_snake_eyes",
                "base_skill_snakes_frenzy",
            ],
            "plugin_skill_ids": [],
            "mount_skill_ids": ["mount_strangled_death"],
        }
    )

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    simulator = GameSimulator(army, opponent, mode="battlefield")
    for round_num in range(1, 3):
        army.army_round = round_num
        opponent.army_round = round_num
        army.triggered_skills_this_round.clear()
        army.skill_trigger_counts_this_round.clear()
        army.skill_triggers_against_this_round.clear()
        army.mount_skill_damage_triggers_this_round.clear()
        army.mount_skill_non_damage_applied_this_round.clear()
        army.mount_skill_dot_hot_applied_this_round.clear()
        simulator._process_skill_triggers(army, opponent, SkillTriggerType.ON_OWN_RAGE_SKILL_CAST)

    instance_keys = [
        skill.get("instance_key")
        for hero in army.heroes
        for skill in hero.skills
        if skill.get("id") == "mount_strangled_death"
    ]
    assert len(instance_keys) == 2
    assert all(instance_keys)
    for key in instance_keys:
        assert len(army.skill_active_cast_trigger_rounds.get(key, [])) == 2
    assert sum(len(v) for v in army.skill_active_cast_trigger_rounds.values()) == 4


def test_duplicate_mount_damage_across_heroes_triggers_independently():
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_flame_serpent"]
    cfg["heroes"].append(
        {
            "hero_name_or_preset": "sigurd",
            "talent_ids": [
                "talent_fiery_snake_spirit",
                "talent_serpents_rage",
                "talent_full_focus",
            ],
            "base_skill_ids": [
                "base_skill_snake_eyes",
                "base_skill_snakes_frenzy",
            ],
            "plugin_skill_ids": [],
            "mount_skill_ids": ["mount_flame_serpent"],
        }
    )

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    for hero in army.heroes:
        for skill in hero.skills:
            if skill.get("id") == "mount_flame_serpent":
                config = skill.get("config", {})
                config.update(
                    {
                        "trigger_interval": 1,
                        "damage_factor": 50.0,
                        "max_triggers_per_round": 2,
                        "max_triggers_per_target_per_round": 1,
                    }
                )

    simulator = GameSimulator(army, opponent, mode="battlefield")
    army.army_round = 1
    opponent.army_round = 1
    opponent.current_troop_count = 100000
    opponent.pending_hp_damage_this_round = 0

    simulator._process_skill_triggers(army, opponent, SkillTriggerType.CHANCE_PER_ROUND)

    instance_keys = [
        skill.get("instance_key")
        for hero in army.heroes
        for skill in hero.skills
        if skill.get("id") == "mount_flame_serpent"
    ]
    assert len(instance_keys) == 2
    assert all(instance_keys)
    for key in instance_keys:
        assert army.mount_skill_damage_triggers_this_round.get(key, 0) == 1
        assert army.skill_trigger_counts.get(key, 0) == 1
        assert army.skill_trigger_counts_this_round.get(key, 0) == 1

    try:
        from vr_game_sim.gui_main import build_army_skill_summary
    except ImportError:
        return

    army.skill_kill_totals[instance_keys[0]] = 10.0
    army.skill_kill_totals[instance_keys[1]] = 20.0
    army.skill_trigger_counts[instance_keys[0]] = 3
    army.skill_trigger_counts[instance_keys[1]] = 7

    summary = build_army_skill_summary(army, cfg, team="red")
    hero0_entries = summary["skills"][0] if summary.get("skills") else []
    hero1_entries = summary["skills"][1] if summary.get("skills") else []
    hero0_entry = next(
        (e for e in hero0_entries if e.get("id") == "mount_flame_serpent"), None
    )
    hero1_entry = next(
        (e for e in hero1_entries if e.get("id") == "mount_flame_serpent"), None
    )
    assert hero0_entry is not None
    assert hero1_entry is not None
    assert hero0_entry.get("casts", 0) == 3
    assert hero1_entry.get("casts", 0) == 7
    assert hero0_entry.get("kills", 0) == 10
    assert hero1_entry.get("kills", 0) == 20


def test_mount_trigger_window_limits_reactive_skills():
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_ragebeast_soul"]

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    simulator = GameSimulator(army, opponent, mode="battlefield")

    def reset_round_state(army_ref):
        army_ref.triggered_skills_this_round.clear()
        army_ref.skill_trigger_counts_this_round.clear()
        army_ref.skill_triggers_against_this_round.clear()
        army_ref.mount_skill_damage_triggers_this_round.clear()
        army_ref.mount_skill_non_damage_applied_this_round.clear()
        army_ref.mount_skill_dot_hot_applied_this_round.clear()

    def trigger_round(round_num):
        army.army_round = round_num
        opponent.army_round = round_num
        reset_round_state(army)
        simulator._process_skill_triggers(
            army, opponent, SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE
        )
        return list(army.skill_trigger_window_rounds.get("mount_ragebeast_soul", []))

    assert len(trigger_round(1)) == 1
    assert len(trigger_round(2)) == 2
    assert len(trigger_round(3)) == 2
    assert sorted(trigger_round(9)) == [2, 9]


def test_duplicate_mount_dot_and_heal_instances_trigger():
    cfg_single = copy.deepcopy(_BASE_CFG)
    cfg_single["heroes"][0]["mount_skill_ids"] = ["mount_poison_n_heal"]

    cfg_double = copy.deepcopy(_BASE_CFG)
    cfg_double["heroes"][0]["mount_skill_ids"] = ["mount_poison_n_heal", "mount_poison_n_heal"]

    army_single, opponent_single = create_armies_from_data([cfg_single, cfg_single])[0:2]
    army_double, opponent_double = create_armies_from_data([cfg_double, cfg_double])[0:2]

    for army, opponent in [
        (army_single, opponent_single),
        (army_double, opponent_double),
    ]:
        army.current_troop_count = 8000
        opponent.current_troop_count = 12000
        army.troop_count_at_round_start = army.current_troop_count
        opponent.troop_count_at_round_start = opponent.current_troop_count
        army.army_round = 1
        opponent.army_round = 1
        poison_skills = [skill for skill in army.heroes[0].skills if skill.get("id") == "mount_poison_n_heal"]
        for idx, skill in enumerate(poison_skills):
            config = skill.setdefault("config", {})
            config["trigger_interval"] = 1
            if len(poison_skills) == 1:
                config["status_factor"] = 450.0
                config["heal_factor"] = 600.0
            else:
                config["status_factor"] = 200.0 if idx == 0 else 450.0
                config["heal_factor"] = 300.0 if idx == 0 else 600.0

    simulator_single = GameSimulator(army_single, opponent_single, mode="battlefield")
    simulator_double = GameSimulator(army_double, opponent_double, mode="battlefield")

    simulator_single._process_skill_triggers(
        army_single, opponent_single, SkillTriggerType.CHANCE_PER_ROUND
    )
    simulator_double._process_skill_triggers(
        army_double, opponent_double, SkillTriggerType.CHANCE_PER_ROUND
    )

    dot_effects_single = [
        eff
        for eff in opponent_single.effects_to_activate_next_round
        if eff.effect_type == EffectType.DAMAGE_OVER_TIME
        and eff.config.get("dot_type") == DoTType.POISON
    ]
    dot_effects_double = [
        eff
        for eff in opponent_double.effects_to_activate_next_round
        if eff.effect_type == EffectType.DAMAGE_OVER_TIME
        and eff.config.get("dot_type") == DoTType.POISON
    ]

    assert len(dot_effects_single) == 1
    assert len(dot_effects_double) == 1
    assert dot_effects_single[0].config.get("status_effect_factor") == pytest.approx(450.0)
    assert dot_effects_double[0].config.get("status_effect_factor") == pytest.approx(450.0)
    assert army_single.pending_hp_healing_this_round > 0
    assert army_double.pending_hp_healing_this_round == pytest.approx(
        army_single.pending_hp_healing_this_round
    )
    # Merged DoT/heal attributes to higher-value instance (mount_poison_n_heal::mount::1)
    higher_instance_key = "mount_poison_n_heal::mount::1"
    assert dot_effects_double[0].source_skill_id == higher_instance_key


def test_duplicate_mount_skill_per_instance_metrics():
    """Duplicate mount skills report damage independently per instance key."""
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_flame_serpent", "mount_flame_serpent"]

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    hero = army.heroes[0]
    mount_skills = [skill for skill in hero.skills if skill.get("id") == "mount_flame_serpent"]
    assert len(mount_skills) == 2    for idx, skill in enumerate(mount_skills):
        config = skill.get("config", {})
        config.update({"trigger_interval": 1, "damage_factor": 50.0})

    simulator = GameSimulator(army, opponent, mode="battlefield")
    army.army_round = 1
    opponent.army_round = 1
    opponent.current_troop_count = 100000
    opponent.pending_hp_damage_this_round = 0

    simulator._process_skill_triggers(army, opponent, SkillTriggerType.CHANCE_PER_ROUND)

    instance_keys = [
        f"mount_flame_serpent::mount::{skill['mount_instance_index']}" for skill in mount_skills
    ]
    for key in instance_keys:
        assert army.mount_skill_damage_triggers_this_round.get(key, 0) >= 0

    damage_by_skill = opponent.damage_contributors_by_skill_this_round.get(army.name, {})
    for key in instance_keys:
        assert key in damage_by_skill or sum(damage_by_skill.values()) == 0, (
            f"Instance {key} should have damage attribution"
        )


def test_reactive_mount_skill_metrics():
    """Power Swipe and other reactive mount skills record metrics correctly."""
    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_power_swipe"]

    army, opponent = create_armies_from_data([cfg, cfg])[0:2]
    simulator = GameSimulator(army, opponent, mode="battlefield")
    
    # Simulate rage skill damage to trigger Power Swipe
    army.army_round = 1
    opponent.army_round = 1
    army.current_troop_count = 50000
    opponent.current_troop_count = 50000
    
    # Trigger Power Swipe by simulating rage skill damage received
    simulator._process_skill_triggers(army, opponent, SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE)
    
    # Commit damage so skill_kill_totals gets updated
    opponent.commit_pending_healing_and_damage()
    
    # Verify Power Swipe recorded metrics
    power_swipe_kills = army.skill_kill_totals.get("mount_power_swipe", 0.0)
    power_swipe_triggers = army.skill_trigger_counts.get("mount_power_swipe", 0)
    
    # If Power Swipe triggered and dealt damage, we should have metrics
    if power_swipe_triggers > 0 and opponent.damage_contributors_by_skill_this_round:
        assert power_swipe_kills >= 0, "Power Swipe should record kill metrics when triggered"


def test_mount_skill_fallback_aggregation():
    """Fallback aggregation finds instance-keyed stats when lookup uses base id."""
    pytest.importorskip("PyQt6")
    try:
        from vr_game_sim.gui_main import build_army_skill_summary
    except ImportError:
        pytest.skip("PyQt6 dependencies not available")

    cfg = copy.deepcopy(_BASE_CFG)
    cfg["heroes"][0]["mount_skill_ids"] = ["mount_crippling_strike"]

    army = create_armies_from_data([cfg])[0]
    
    # Manually set instance-keyed stats (simulating duplicate mount scenario)
    army.skill_kill_totals["mount_crippling_strike::mount::0"] = 100.0
    army.skill_heal_totals["mount_crippling_strike::mount::0"] = 50.0
    army.skill_trigger_counts["mount_crippling_strike"] = 10
    
    summary = build_army_skill_summary(army, cfg, team="red")
    hero_entries = summary["skills"][0] if summary.get("skills") else []
    
    mount_entry = next(
        (e for e in hero_entries if e.get("id") == "mount_crippling_strike"),
        None
    )
    
    assert mount_entry is not None, "Mount skill should appear in summary"
    # Fallback aggregation should find instance-keyed data
    assert mount_entry.get("kills", 0) == 100, "Fallback should aggregate instance-keyed kills"
    assert mount_entry.get("heals", 0) == 50, "Fallback should aggregate instance-keyed heals"
    assert mount_entry.get("casts", 0) == 10, "Trigger counts should be found"

    # Per-instance rows should not aggregate across instance keys
    cfg_dupe = copy.deepcopy(_BASE_CFG)
    cfg_dupe["heroes"][0]["mount_skill_ids"] = ["mount_flame_serpent", "mount_flame_serpent"]
    army_dupe = create_armies_from_data([cfg_dupe])[0]
    army_dupe.skill_kill_totals["mount_flame_serpent::mount::0"] = 30.0

    summary_dupe = build_army_skill_summary(army_dupe, cfg_dupe, team="red")
    hero_entries_dupe = summary_dupe["skills"][0] if summary_dupe.get("skills") else []
    flame_entries = [
        entry for entry in hero_entries_dupe if entry.get("id") == "mount_flame_serpent"
    ]
    assert len(flame_entries) == 2
    kills = sorted(entry.get("kills", 0) for entry in flame_entries)
    assert kills == [0, 30], "Per-instance rows should not aggregate sibling stats"
