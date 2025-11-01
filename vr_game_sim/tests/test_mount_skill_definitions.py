import json
from pathlib import Path

import pytest

from vr_game_sim.mount_skill_definitions import (
    MOUNT_SKILL_DEFINITIONS,
    _slugify,
)


@pytest.mark.parametrize("entry", json.loads(Path("vr_game_sim/Descriptions/MountSkillsBehaviors.json").read_text()))
def test_mount_skill_troop_types_match_metadata(entry):
    skill_id = f"mount_{entry.get('type', 'command').lower()}_{_slugify(entry.get('name', ''))}"
    skill_def = MOUNT_SKILL_DEFINITIONS.get(skill_id)
    assert skill_def is not None, f"missing registry entry for {skill_id}"

    troop_types = entry.get("troop_types")
    assert troop_types, f"expected troop types for {entry.get('name')}"
    config_types = skill_def.get("config", {}).get("troop_types")
    assert config_types == troop_types


@pytest.mark.parametrize(
    "skill_id",
    [
        "mount_command_firewing_ashes",
        "mount_command_crippling_strike",
        "mount_command_bonegnaw_bug",
    ],
)
def test_mount_skill_effect_durations_follow_round_convention(skill_id):
    skill_def = MOUNT_SKILL_DEFINITIONS[skill_id]
    for effect in skill_def.get("config", {}).get("self_effects", []) + skill_def.get(
        "config", {}
    ).get("enemy_effects", []):
        duration_rounds = effect.get("duration_rounds")
        if duration_rounds is None:
            continue
        expected_duration = duration_rounds - 1 if duration_rounds > 0 else duration_rounds
        assert (
            effect.get("duration") == expected_duration
        ), f"Duration mismatch for {skill_id}: {effect}"
