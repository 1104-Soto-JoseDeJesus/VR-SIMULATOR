import copy
import json

from vr_game_sim.main import save_army_to_file
from vr_game_sim.skill_definitions import (
    SKILL_REGISTRY_GLOBAL,
    build_skill_registry_with_overrides,
)
from vr_game_sim.skill_override_utils import diff_structures


def test_plugin_skill_override_list_serializes(tmp_path):
    base_definition = copy.deepcopy(SKILL_REGISTRY_GLOBAL["plugin_divine_shield"])
    modified_definition = copy.deepcopy(base_definition)
    new_magnitude = 0.42
    modified_definition["effects_to_apply"][0]["magnitude"] = new_magnitude

    overrides = diff_structures(base_definition, modified_definition)
    assert overrides is not None
    assert overrides["effects_to_apply"][0]["magnitude"] == new_magnitude

    army_payload = {
        "army_name": "Serialization Test",
        "unit_type": "infantry",
        "tier": 5,
        "count": 1,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.65,
        "heroes": [
            {
                "hero_name_or_preset": "Custom",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": ["plugin_divine_shield"],
                "skill_overrides": {"plugin_divine_shield": overrides},
            }
        ],
    }

    target_path = tmp_path / "army.json"
    save_army_to_file(army_payload, target_path)

    saved = json.loads(target_path.read_text())
    saved_overrides = saved["heroes"][0]["skill_overrides"]
    effects_override = saved_overrides["plugin_divine_shield"]["effects_to_apply"]
    assert effects_override["0"]["magnitude"] == new_magnitude

    registry = build_skill_registry_with_overrides(saved_overrides)
    applied = registry["plugin_divine_shield"]["effects_to_apply"][0]
    assert applied["magnitude"] == new_magnitude
    assert applied["effect_type"] == base_definition["effects_to_apply"][0]["effect_type"]


def test_diff_structures_handles_list_shrink():
    base = [1, 2, 3]
    modified = [1, 2]

    diff = diff_structures(base, modified)

    assert diff == modified
