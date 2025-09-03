import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_DELAYED_RAGE_REDUCTION
from vr_game_sim.skill_logic.plugin_skill_handlers import (
    handle_plugin_blessed_negation,
    handle_plugin_lokis_trick,
)


def test_skill_rage_reduction_totals_tracks_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    defender.current_rage = 200
    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
        "duration": 0,
        "config": {"rage_reduction": 150},
    }
    eff = defender._create_and_add_single_effect(effect_data, "test_rr", attacker, defender)
    defender.active_effects.append(eff)

    defender.apply_start_of_round_rage_deductions()

    assert attacker.skill_rage_reduction_totals.get("test_rr", 0) == 150
    assert defender.skill_rage_reduction_totals.get("test_rr", 0) == 0
    assert defender.current_rage == 50


def test_blessed_negation_rage_reduction_tracked_for_caster():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    defender.current_rage = 200
    sim.round = 1
    skill_def = {
        "id": "plugin_blessed_negation",
        "name": "Blessed Negation",
        "config": {"trigger_interval": 1, "damage_factor": 0.0, "rage_reduction": 100},
    }

    handle_plugin_blessed_negation(attacker, defender, skill_def, None, sim)
    if defender.effects_to_activate_next_round:
        defender.upcoming_effects.extend(defender.effects_to_activate_next_round)
        defender.effects_to_activate_next_round.clear()
    defender.activate_queued_effects()
    defender.apply_start_of_round_rage_deductions()

    assert attacker.skill_rage_reduction_totals.get("plugin_blessed_negation", 0) == 100
    assert defender.skill_rage_reduction_totals.get("plugin_blessed_negation", 0) == 0
    assert defender.current_rage == 100


def test_lokis_trick_rage_reduction_tracked_for_caster():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    defender.current_rage = 200
    sim.round = 1
    skill_def = {
        "id": "plugin_lokis_trick",
        "name": "Loki's Trick",
        "config": {
            "damage_factor": 100.0,
            "rage_reduction_chance": 1.0,
            "rage_reduction_amount": 80.0,
            "buff_removal_chance": 0.0,
        },
    }

    handle_plugin_lokis_trick(attacker, defender, skill_def, None, sim)
    if defender.effects_to_activate_next_round:
        defender.upcoming_effects.extend(defender.effects_to_activate_next_round)
        defender.effects_to_activate_next_round.clear()
    defender.activate_queued_effects()
    defender.apply_start_of_round_rage_deductions()

    assert attacker.skill_rage_reduction_totals.get("plugin_lokis_trick", 0) == 80
    assert defender.skill_rage_reduction_totals.get("plugin_lokis_trick", 0) == 0
    assert defender.current_rage == 120
