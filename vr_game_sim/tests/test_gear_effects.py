import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import StatType
from vr_game_sim.gear_definitions import normalize_gear_id
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def test_normalize_gear_id_accepts_aliases():
    assert (
        normalize_gear_id("Legendary - Immolated Axe")
        == "gear_immolated_axe_legendary"
    )
    assert normalize_gear_id("Immolated Axe (Epic)") == "gear_immolated_axe_epic"


def test_gear_effects_applied_to_army():
    unit = Unit("archers", 5, initial_count=1000)
    hero = Hero(
        "Tester",
        ["dummy_talent_empty"] * 3,
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
        gear_config={
            "weapon": "Legendary - Immolated Axe",
            "head": "Legendary - Blazing Helmet",
        },
    )
    army = Army("Test Army", unit, heroes=[hero])

    gear_effects = [
        eff
        for eff in army.active_effects
        if eff.config.get("gear_id")
        in {"gear_immolated_axe_legendary", "gear_blazing_helmet_legendary"}
    ]

    assert len(gear_effects) == 3

    effect_lookup = {
        (effect.config["gear_id"], effect.config.get("stat_to_mod")): effect.magnitude
        for effect in gear_effects
    }

    assert effect_lookup[("gear_immolated_axe_legendary", StatType.BASIC_DAMAGE_ADJUST)] == pytest.approx(
        0.10
    )
    assert effect_lookup[("gear_immolated_axe_legendary", StatType.COUNTER_DAMAGE_ADJUST)] == pytest.approx(
        0.0675
    )
    assert effect_lookup[("gear_blazing_helmet_legendary", StatType.GENERAL_DAMAGE_MODIFIER)] == pytest.approx(
        0.0325
    )

    for effect in gear_effects:
        assert effect.duration == -1
        assert effect.config.get("is_dispellable") is False
