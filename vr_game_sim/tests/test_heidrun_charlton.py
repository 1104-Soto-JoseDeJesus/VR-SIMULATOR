import random

import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import EffectType, StatType, DoTType
from vr_game_sim.constants import (
    EFFECT_NAME_RETURNING_BLOOD_FLAME_EDGE_BURN,
    EFFECT_NAME_ARMOR_CORRODING_BLOOD_POISON,
    EFFECT_NAME_ARMOR_CORRODING_BLOOD_DMG_RED,
    EFFECT_NAME_PENDING_ARMOR_CORRODING_BLOOD_DISPEL,
    EFFECT_NAME_DANCE_OF_DEATH_POISON,
    EFFECT_NAME_FORESIGHT_BURN,
)
from vr_game_sim.skill_logic.talent_handlers import (
    handle_talent_armor_corroding_blood,
    handle_talent_returning_blood_flame_edge,
)
from vr_game_sim.skill_logic.base_skill_handlers import handle_base_skill_foresight
from vr_game_sim.skill_logic.rage_skill_handlers import handle_rage_dance_of_death


def _make_armies(mode: str = "standard"):
    attacker_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker_unit.base_atk_stat = 3000
    defender_unit.base_def_stat = 300
    attacker = Army(name="Attacker", unit=attacker_unit)
    defender = Army(name="Defender", unit=defender_unit)
    sim = GameSimulator(attacker, defender, track_stats=False, mode=mode)
    return attacker, defender, sim


def _activate(army: Army) -> None:
    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()


def _add_active_dot(army: Army, name: str, dot_type: DoTType, owner: Army) -> None:
    army._create_and_add_single_effect(
        {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": name,
            "dot_type": dot_type,
            "status_effect_factor": 200.0,
            "duration": 2,
        },
        "test_setup",
        owner,
        army,
        owner,
    )
    _activate(army)


def test_presets_load_five_skills():
    for hero_key in ("heidrun", "charlton"):
        preset = HERO_PRESETS[hero_key]
        hero = Hero(
            hero_key,
            list(preset["talents"]),
            list(preset["base_skills"]),
            list(preset["plugin_skills"]),
            SKILL_REGISTRY_GLOBAL,
        )
        resolved = [s for s in hero.skills if s["id"] != "dummy_talent_empty"]
        assert len(resolved) == 5


def test_heidrun_passive_applies_permanent_boosts():
    attacker_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    hero = Hero("Heidrun", ["talent_bloody_slash_venomous_bite"], [], [], SKILL_REGISTRY_GLOBAL)
    attacker = Army(name="Attacker", unit=attacker_unit, heroes=[hero])
    defender = Army(name="Defender", unit=defender_unit)
    GameSimulator(attacker, defender, track_stats=False)
    _activate(attacker)

    assert attacker.get_sum_stat_magnitudes(StatType.RAGE_SKILL_DAMAGE_MODIFIER) == pytest.approx(0.20)
    assert attacker.get_sum_stat_magnitudes(StatType.POISON_DAMAGE_BOOST) == pytest.approx(0.20)


def test_charlton_passive_applies_permanent_boosts():
    attacker_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    hero = Hero("Charlton", ["talent_eagle_flame_pursuit"], [], [], SKILL_REGISTRY_GLOBAL)
    attacker = Army(name="Attacker", unit=attacker_unit, heroes=[hero])
    defender = Army(name="Defender", unit=defender_unit)
    GameSimulator(attacker, defender, track_stats=False)
    _activate(attacker)

    assert attacker.get_sum_stat_magnitudes(StatType.RAGE_SKILL_DAMAGE_MODIFIER) == pytest.approx(0.20)
    assert attacker.get_sum_stat_magnitudes(StatType.BURN_DAMAGE_BOOST) == pytest.approx(0.20)


def test_returning_blood_flame_edge_fires_on_interval():
    random.seed(1)
    attacker, defender, sim = _make_armies()
    attacker.army_round = 6
    skill_def = SKILL_REGISTRY_GLOBAL["talent_returning_blood_flame_edge"]
    happened, _ = handle_talent_returning_blood_flame_edge(attacker, defender, skill_def, None, sim)
    assert happened
    burns = [
        e for e in defender.effects_to_activate_next_round
        if e.name == EFFECT_NAME_RETURNING_BLOOD_FLAME_EDGE_BURN
    ]
    assert len(burns) == 1


def test_returning_blood_flame_edge_skips_off_interval():
    attacker, defender, sim = _make_armies()
    attacker.army_round = 5
    skill_def = SKILL_REGISTRY_GLOBAL["talent_returning_blood_flame_edge"]
    happened, logs = handle_talent_returning_blood_flame_edge(attacker, defender, skill_def, None, sim)
    assert not happened
    assert logs == []
    assert not any(
        e.name == EFFECT_NAME_RETURNING_BLOOD_FLAME_EDGE_BURN
        for e in defender.effects_to_activate_next_round
    )


def test_armor_corroding_blood_applies_poison_and_damage_reduction():
    attacker, defender, sim = _make_armies()
    skill_def = SKILL_REGISTRY_GLOBAL["talent_armor_corroding_blood"]
    happened, _ = handle_talent_armor_corroding_blood(attacker, defender, skill_def, None, sim)
    assert happened

    poison = [
        e for e in defender.effects_to_activate_next_round
        if e.name == EFFECT_NAME_ARMOR_CORRODING_BLOOD_POISON
    ]
    assert len(poison) == 1

    dmg_red = [
        e for e in attacker.effects_to_activate_next_round
        if e.name == EFFECT_NAME_ARMOR_CORRODING_BLOOD_DMG_RED
    ]
    assert len(dmg_red) == 1
    assert dmg_red[0].magnitude == pytest.approx(-0.30)


def test_armor_corroding_blood_dispels_buff_when_enemy_burning():
    attacker, defender, sim = _make_armies()
    _add_active_dot(defender, "Test Burn", DoTType.BURN, attacker)
    defender._create_and_add_single_effect(
        {
            "effect_type": EffectType.STAT_MOD,
            "name": "Test Buff",
            "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
            "magnitude": 0.20,
            "duration": 3,
        },
        "test_setup",
        defender,
        defender,
        attacker,
    )
    _activate(defender)

    skill_def = SKILL_REGISTRY_GLOBAL["talent_armor_corroding_blood"]
    handle_talent_armor_corroding_blood(attacker, defender, skill_def, None, sim)

    dispel = [
        e for e in defender.effects_to_activate_next_round
        if e.name == EFFECT_NAME_PENDING_ARMOR_CORRODING_BLOOD_DISPEL
    ]
    assert len(dispel) == 1


def test_dance_of_death_bonus_damage_only_when_already_poisoned():
    skill_def = SKILL_REGISTRY_GLOBAL["rage_skill_dance_of_death"]

    # Not poisoned before the skill: no bonus damage branch.
    attacker, defender, sim = _make_armies()
    _, logs_clean, _ = handle_rage_dance_of_death(attacker, defender, skill_def, {}, sim)
    assert not any("additional damage" in text for text, _ in logs_clean)
    assert any(
        e.name == EFFECT_NAME_DANCE_OF_DEATH_POISON
        for e in defender.effects_to_activate_next_round
    )

    # Already poisoned before the skill: bonus damage branch fires.
    attacker2, defender2, sim2 = _make_armies()
    _add_active_dot(defender2, "Pre Poison", DoTType.POISON, attacker2)
    _, logs_poisoned, _ = handle_rage_dance_of_death(attacker2, defender2, skill_def, {}, sim2)
    assert any("additional damage" in text for text, _ in logs_poisoned)


def test_foresight_flank_bonus_only_when_flanked():
    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_foresight"]

    # Standard duel mode: burn only, no flank bonus.
    attacker, defender, sim = _make_armies(mode="standard")
    attacker.army_round = 9
    _, logs_duel = handle_base_skill_foresight(attacker, defender, skill_def, None, sim)
    assert any(
        e.name == EFFECT_NAME_FORESIGHT_BURN
        for e in defender.effects_to_activate_next_round
    )
    assert not any("Flanked" in text for text, _ in logs_duel)

    # Battlefield mode with 2+ direct attackers: flank bonus applies.
    attacker2, defender2, sim2 = _make_armies(mode="battlefield")
    attacker2.army_round = 9
    sim2.parent_engine = type(
        "DummyEngine", (), {"get_direct_attackers": lambda self, _: [defender2, object()]}
    )()
    _, logs_flank = handle_base_skill_foresight(attacker2, defender2, skill_def, None, sim2)
    assert any("Flanked" in text for text, _ in logs_flank)
