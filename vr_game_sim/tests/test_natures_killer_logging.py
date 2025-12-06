from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder
from vr_game_sim.enums import EffectType, DoTType
from vr_game_sim.constants import EFFECT_NAME_NATURES_KILLER_POISON


def test_natures_killer_dot_logs_with_skill_name_and_damage():
    attacker_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker_unit.base_atk_stat = 2400
    defender_unit.base_def_stat = 400

    attacker = Army(name="Attacker", unit=attacker_unit)
    defender = Army(name="Defender", unit=defender_unit)

    report_builder = ReportBuilder(use_color=False)
    sim = GameSimulator(attacker, defender, report_builder)

    effect_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_NATURES_KILLER_POISON,
        "dot_type": DoTType.POISON,
        "status_effect_factor": 500.0,
        "duration": 1,
    }

    effect = defender._create_and_add_single_effect(
        effect_data,
        "talent_natures_killer",
        attacker,
        defender,
        attacker,
    )
    assert effect is not None

    if defender.effects_to_activate_next_round:
        defender.upcoming_effects.extend(defender.effects_to_activate_next_round)
        defender.effects_to_activate_next_round.clear()

    defender.activate_queued_effects()

    effect.applied_this_round = False

    defender.process_periodic_effects("start_of_round", opponent=attacker)

    log_entries = sim.round_skill_triggers_log[defender.name]
    natures_killer_entries = [
        entry for entry in log_entries if entry.get("skill_name") == "Nature's Killer"
    ]
    assert natures_killer_entries, "Expected Nature's Killer to log DoT damage"
    assert natures_killer_entries[-1].get("damage_done_hp", 0) > 0

    report_builder.emit_round(1, sim.round_combat_actions_log, sim.round_skill_triggers_log)
    round_data = report_builder.get_rounds()[0]
    skill_triggers = round_data["skill_triggers"][defender.name]
    assert any(
        entry.get("skill_name") == "Nature's Killer" and entry.get("damage_done_hp", 0) > 0
        for entry in skill_triggers
    )
