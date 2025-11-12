import pytest

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import EffectType, DoTType
from vr_game_sim.constants import EFFECT_NAME_FIERY_RAGE_BURN
from vr_game_sim.report_builder import ReportBuilder


@pytest.mark.parametrize("status_factor", [350.0, 700.0])
def test_dot_skills_report_potential_kills(status_factor):
    attacker_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    defender_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    attacker_unit.base_atk_stat = 2400
    defender_unit.base_def_stat = 400

    attacker = Army(name="Attacker", unit=attacker_unit)
    defender = Army(name="Defender", unit=defender_unit)

    sim = GameSimulator(attacker, defender)

    effect_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_FIERY_RAGE_BURN,
        "dot_type": DoTType.BURN,
        "status_effect_factor": status_factor,
        "duration": 1,
    }

    effect = defender._create_and_add_single_effect(
        effect_data,
        "plugin_fiery_rage",
        attacker,
        defender,
        attacker,
    )
    assert effect is not None

    if defender.effects_to_activate_next_round:
        defender.upcoming_effects.extend(defender.effects_to_activate_next_round)
        defender.effects_to_activate_next_round.clear()

    defender.activate_queued_effects()

    # The first tick happens on the next round after application.
    effect.applied_this_round = False

    defender.process_periodic_effects("start_of_round", opponent=attacker)

    log_entries = sim.round_skill_triggers_log[defender.name]
    burn_entries = [entry for entry in log_entries if entry.get("skill_name") == EFFECT_NAME_FIERY_RAGE_BURN]
    assert burn_entries, "Expected Fiery Rage burn to produce a log entry"
    kills = burn_entries[-1].get("potential_kills", 0)
    assert kills > 0

    defender.commit_pending_healing_and_damage()

    assert attacker.skill_kill_totals.get("plugin_fiery_rage", 0.0) > 0.0

    report_builder = ReportBuilder(use_color=False)
    report_builder.emit_round(1, sim.round_combat_actions_log, sim.round_skill_triggers_log)
    report_text = report_builder.get_report_text()
    assert f"Kills {kills}" in report_text
