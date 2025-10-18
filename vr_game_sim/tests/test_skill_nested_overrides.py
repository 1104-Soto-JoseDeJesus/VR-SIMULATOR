import copy

from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import (
    SKILL_REGISTRY_GLOBAL,
    build_skill_registry_with_overrides,
)


def test_nested_skill_overrides_are_applied():
    shield_override_value = 1337.0
    revenge_magnitude = 0.45
    aura_rage_gain = 150.0

    shield_effects = copy.deepcopy(
        SKILL_REGISTRY_GLOBAL["talent_shield_of_resistance"]["effects_to_apply"]
    )
    shield_effects[0]["shield_factor"] = shield_override_value

    revenge_config = copy.deepcopy(
        SKILL_REGISTRY_GLOBAL["talent_revenge_echo"]["config"]
    )
    revenge_config["conditional_buff"]["magnitude"] = revenge_magnitude

    first_strike_config = copy.deepcopy(
        SKILL_REGISTRY_GLOBAL["plugin_first_strike"]["config"]
    )
    first_strike_config["aura_effect_definition"]["config"][
        "rage_per_round"
    ] = aura_rage_gain

    overrides = {
        "talent_shield_of_resistance": {"effects_to_apply": shield_effects},
        "talent_revenge_echo": {"config": revenge_config},
        "plugin_first_strike": {"config": first_strike_config},
    }

    registry = build_skill_registry_with_overrides(overrides)

    hero = Hero(
        "Override Tester",
        ["talent_shield_of_resistance", "talent_revenge_echo"],
        [],
        ["plugin_first_strike"],
        registry,
    )

    shield_skill = next(s for s in hero.skills if s["id"] == "talent_shield_of_resistance")
    revenge_skill = next(s for s in hero.skills if s["id"] == "talent_revenge_echo")
    first_strike_skill = next(s for s in hero.skills if s["id"] == "plugin_first_strike")

    assert (
        shield_skill["effects_to_apply"][0]["shield_factor"]
        == shield_override_value
    )
    assert (
        shield_skill["effects_to_apply"][0]["effect_type"]
        == SKILL_REGISTRY_GLOBAL["talent_shield_of_resistance"]["effects_to_apply"][0][
            "effect_type"
        ]
    )

    assert (
        revenge_skill["config"]["conditional_buff"]["magnitude"]
        == revenge_magnitude
    )
    assert (
        revenge_skill["config"]["conditional_buff"]["name"]
        == SKILL_REGISTRY_GLOBAL["talent_revenge_echo"]["config"][
            "conditional_buff"
        ]["name"]
    )

    assert (
        first_strike_skill["config"]["aura_effect_definition"]["config"][
            "rage_per_round"
        ]
        == aura_rage_gain
    )
    assert (
        first_strike_skill["config"]["aura_effect_definition"]["duration"]
        == SKILL_REGISTRY_GLOBAL["plugin_first_strike"]["config"][
            "aura_effect_definition"
        ]["duration"]
    )
