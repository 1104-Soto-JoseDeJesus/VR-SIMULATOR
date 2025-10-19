import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType, StatType
from vr_game_sim.constants import EFFECT_NAME_SOUL_AWAKENING_COUNTER_REDUCTION
from vr_game_sim.skill_logic.talent_handlers import handle_talent_soul_awakening


def test_skill_damage_reduction_totals_tracks_units():
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1000
    dfd_unit.base_def_stat = 1
    attacker = Army(name="A", unit=atk_unit)
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)

    effect_data = {
        "name": "Test DR",
        "effect_type": EffectType.STAT_MOD,
        "config": {"stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER},
        "magnitude": -0.5,
    }
    eff = defender._create_and_add_single_effect(effect_data, "test_dr", defender, defender)
    defender.active_effects.append(eff)

    sim._calculate_and_log_attack(attacker, defender, is_counter=False)

    assert defender.skill_damage_reduction_totals.get("test_dr", 0) > 0


def test_soul_awakening_counter_reduction_only_affects_counter_damage():
    reduction = -0.45

    def compute_damage(is_counter: bool, apply_effect: bool):
        counter_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
        defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)

        counter_unit.base_atk_stat = 1200
        defender_unit.base_def_stat = 150
        defender_unit.base_hp_stat = 200

        counter_army = Army(name="Counter", unit=counter_unit)
        defender_army = Army(name="Soul", unit=defender_unit)

        simulator = GameSimulator(counter_army, defender_army, track_stats=False)

        applied_effect = None
        if apply_effect:
            skill_def = {
                "id": "talent_soul_awakening",
                "config": {"counter_reduction": reduction},
            }
            happened, _ = handle_talent_soul_awakening(
                defender_army, counter_army, skill_def, None, simulator
            )
            assert happened
            assert defender_army.upcoming_effects
            defender_army.active_effects.extend(defender_army.upcoming_effects)
            defender_army.upcoming_effects.clear()
            applied_effect = defender_army.active_effects[-1]

        damage, _, _, _ = simulator._calculate_and_log_attack(
            counter_army, defender_army, is_counter=is_counter
        )
        return damage, applied_effect

    baseline_counter_damage, _ = compute_damage(is_counter=True, apply_effect=False)
    reduced_counter_damage, effect_instance = compute_damage(
        is_counter=True, apply_effect=True
    )

    assert effect_instance is not None
    assert effect_instance.name == EFFECT_NAME_SOUL_AWAKENING_COUNTER_REDUCTION
    assert effect_instance.config.get("stat_to_mod") == StatType.DAMAGE_TAKEN_MULTIPLIER
    assert effect_instance.config.get("config_filter") == {"attack_type": "COUNTER"}

    expected_damage = baseline_counter_damage * (1.0 + reduction)
    assert reduced_counter_damage == pytest.approx(expected_damage, rel=1e-3)

    baseline_basic_damage, _ = compute_damage(is_counter=False, apply_effect=False)
    basic_damage_with_effect, _ = compute_damage(is_counter=False, apply_effect=True)

    assert basic_damage_with_effect == pytest.approx(baseline_basic_damage, rel=1e-6)
