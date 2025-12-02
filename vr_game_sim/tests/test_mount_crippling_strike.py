import random

import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import PluginSkillLabel, SkillTriggerType, StatType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def _reset_round_state(army: Army) -> None:
    army.triggered_skills_this_round.clear()
    army.skill_trigger_counts_this_round.clear()
    army.skill_triggers_against_this_round.clear()
    army.pending_hp_damage_this_round = 0


def _build_army_with_crippling_strike() -> Army:
    hero = Hero(
        "Rider",
        ["dummy_talent_empty"] * 3,
        ["mount_crippling_strike"],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    return Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero])


def test_crippling_strike_passive_crit_bonus_applied():
    army1 = _build_army_with_crippling_strike()
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    GameSimulator(army1, army2)

    crit_rate = army1.get_sum_stat_magnitudes(
        StatType.COMMAND_SKILL_CRIT_RATE,
        attack_type_filter="SKILL",
        skill_label=PluginSkillLabel.COMMAND.value,
    )
    assert crit_rate == pytest.approx(0.02)


def test_crippling_strike_triggers_every_six_rounds():
    random.seed(1)
    army1 = _build_army_with_crippling_strike()
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)

    trigger_rounds: list[int] = []
    detailed_logs: list[str] = []

    for round_no in range(1, 13):
        army1.army_round = round_no
        army2.army_round = round_no
        sim.round = round_no
        sim.round_skill_triggers_log = {army1.name: [], army2.name: []}
        _reset_round_state(army1)
        _reset_round_state(army2)

        sim._process_skill_triggers(army1, army2, SkillTriggerType.CHANCE_PER_ROUND)

        round_logs = sim.round_skill_triggers_log[army1.name]
        if round_logs:
            trigger_rounds.append(round_no)
            detailed_logs.extend(
                entry["effect_description"]
                for entry in round_logs
                if "Factor" in entry.get("effect_description", "")
            )

    assert trigger_rounds == [6, 12]
    assert all("Factor: 780.0" in log for log in detailed_logs)
