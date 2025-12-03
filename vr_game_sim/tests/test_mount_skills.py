import copy

from vr_game_sim.enums import SkillType
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
        if "rage_gain" in expectations:
            assert config.get("rage_gain") == expectations["rage_gain"]
