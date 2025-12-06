from vr_game_sim.army_composition import Army
from vr_game_sim.constants import (
    EFFECT_NAME_NATURE_MARK,
    EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
    EFFECT_NAME_NATURE_BLESSING_EVASION,
    EFFECT_NAME_NATURES_KILLER_POISON,
    EFFECT_NAME_NATURES_KILLER_BURN,
)
from vr_game_sim.enums import EffectType, StatType, DoTType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.base_skill_handlers import handle_base_skill_nature_blessing
from vr_game_sim.skill_logic.talent_handlers import handle_talent_natures_killer
from vr_game_sim.unit_definition import Unit


def _activate_next_round_effects(army: Army) -> None:
    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()


def _create_nature_mark(army: Army) -> None:
    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_NATURE_MARK,
        "duration": -1,
        "activate_next_round": True,
    }
    army._create_and_add_single_effect(effect_data, "test_skill", army, army, army)


def test_nature_marks_stack_without_replacement():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="Army", unit=unit)

    _create_nature_mark(army)
    _create_nature_mark(army)

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    active_mark_count = sum(1 for eff in army.active_effects if eff.name == EFFECT_NAME_NATURE_MARK)
    assert active_mark_count == 2


def test_nature_marks_not_dispelled_by_enemy_effects():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    enemy_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="Army", unit=unit)
    enemy = Army(name="Enemy", unit=enemy_unit)
    GameSimulator(army, enemy)

    _create_nature_mark(army)
    _create_nature_mark(army)

    buff = {
        "effect_type": EffectType.STAT_MOD,
        "name": "Temporary Buff",
        "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
        "magnitude": 0.10,
        "duration": 1,
    }
    created_buff = army._create_and_add_single_effect(buff, "buff_skill", army, army, enemy)
    assert created_buff is not None

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    dispellable = [eff for eff in army.active_effects if eff.is_dispellable_buff_candidate()]
    assert len(dispellable) == 1

    dispel_effect = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
        "duration": 0,
        "config": {"buff_ids_to_remove": [dispellable[0].id]},
        "activate_next_round": True,
    }
    army._create_and_add_single_effect(dispel_effect, "dispel_skill", enemy, army, enemy)

    _activate_next_round_effects(army)
    army.activate_queued_effects()
    army.process_periodic_effects("start_of_round", opponent=enemy)

    active_mark_count = sum(1 for eff in army.active_effects if eff.name == EFFECT_NAME_NATURE_MARK)
    assert active_mark_count == 2
    assert not any(eff.name == "Temporary Buff" for eff in army.active_effects)


def test_nature_blessing_threshold_triggers_and_consumes_marks_at_evasion():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    enemy_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="Army", unit=unit)
    enemy = Army(name="Enemy", unit=enemy_unit)
    simulator = GameSimulator(army, enemy)
    army.army_round = 9
    simulator.round = 9

    for _ in range(15):
        _create_nature_mark(army)

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_nature_blessing"]
    happened, _ = handle_base_skill_nature_blessing(army, enemy, skill_def, None, simulator)
    assert happened

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    evasion_effects = [eff for eff in army.active_effects if eff.name == EFFECT_NAME_NATURE_BLESSING_EVASION]
    assert evasion_effects, "Evasion buff should be applied when evasion threshold is met"

    remaining_marks = [eff for eff in army.active_effects if eff.name == EFFECT_NAME_NATURE_MARK]
    assert len(remaining_marks) == 1, "Only the newly added mark should remain after evasion triggers"


def test_natures_killer_thresholds_use_stacked_marks_without_removing_them():
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    enemy_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="Army", unit=unit)
    enemy = Army(name="Enemy", unit=enemy_unit)
    simulator = GameSimulator(army, enemy)
    army.army_round = 6
    simulator.round = 6

    for _ in range(12):
        _create_nature_mark(army)

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    skill_def = SKILL_REGISTRY_GLOBAL["talent_natures_killer"]
    happened, _ = handle_talent_natures_killer(army, enemy, skill_def, None, simulator)
    assert happened

    _activate_next_round_effects(enemy)
    enemy.activate_queued_effects()

    poison_effects = [eff for eff in enemy.active_effects if eff.name == EFFECT_NAME_NATURES_KILLER_POISON]
    burn_effects = [eff for eff in enemy.active_effects if eff.name == EFFECT_NAME_NATURES_KILLER_BURN]
    assert poison_effects, "Nature's Killer should apply poison when threshold is met"
    assert burn_effects, "Nature's Killer should apply burn when burn threshold is met"

    remaining_marks = [eff for eff in army.active_effects if eff.name == EFFECT_NAME_NATURE_MARK]
    assert len(remaining_marks) == 12

