import pytest

from vr_game_sim.constants import EFFECT_NAME_ON_ALERT_COUNTER_BUFF
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.main import create_armies_from_data


def _on_alert_army_config():
    return {
        "army_name": "OnAlertArmy",
        "unit_type": "infantry",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [
            {
                "hero_name_or_preset": "Tester",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": ["plugin_on_alert"],
                "skill_overrides": {},
            }
        ],
        "team": "red",
        "speed": 50.0,
    }


def _create_simulator_with_on_alert():
    army = create_armies_from_data([_on_alert_army_config()])[0]
    enemy = Army("Enemy", Unit("infantry", 5, initial_count=10), heroes=[])
    simulator = GameSimulator(army, enemy)
    return army, enemy, simulator


def _get_on_alert_skill(army):
    return next(skill for skill in army.heroes[0].skills if skill["id"] == "plugin_on_alert")


def _activate_next_round_effects(army):
    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()


def test_on_alert_applies_next_round_and_is_not_dispellable():
    army, enemy, simulator = _create_simulator_with_on_alert()
    skill = _get_on_alert_skill(army)

    simulator.round = army.army_round = 9
    happened, logs = skill["logic_handler"](army, enemy, skill, None, simulator)

    assert happened
    assert any(
        eff.name == EFFECT_NAME_ON_ALERT_COUNTER_BUFF
        for eff in army.effects_to_activate_next_round
    )
    assert not any(
        eff.name == EFFECT_NAME_ON_ALERT_COUNTER_BUFF for eff in army.active_effects
    )
    assert "now +17%" in logs[0][0]

    _activate_next_round_effects(army)

    active_buffs = [
        eff for eff in army.active_effects if eff.name == EFFECT_NAME_ON_ALERT_COUNTER_BUFF
    ]
    assert len(active_buffs) == 1
    assert active_buffs[0].config.get("is_dispellable", True) is False
    assert active_buffs[0].config.get("stack_count") == 1
    assert active_buffs[0].magnitude == pytest.approx(0.17)


def test_on_alert_stacks_and_caps_at_five():
    army, enemy, simulator = _create_simulator_with_on_alert()
    skill = _get_on_alert_skill(army)

    total_rounds = [9, 18, 27, 36, 45]
    for index, round_number in enumerate(total_rounds):
        simulator.round = army.army_round = round_number
        happened, logs = skill["logic_handler"](army, enemy, skill, None, simulator)
        assert happened
        if index == 0:
            assert "now +17%" in logs[0][0]
        elif index == 1:
            assert "now +34%" in logs[0][0]
        _activate_next_round_effects(army)

    active_buffs = [
        eff for eff in army.active_effects if eff.name == EFFECT_NAME_ON_ALERT_COUNTER_BUFF
    ]
    assert len(active_buffs) == 1
    assert active_buffs[0].config.get("stack_count") == 5
    assert active_buffs[0].magnitude == pytest.approx(0.85)

    simulator.round = army.army_round = 54
    happened, _ = skill["logic_handler"](army, enemy, skill, None, simulator)
    assert not happened
    assert not any(
        eff.name == EFFECT_NAME_ON_ALERT_COUNTER_BUFF
        for eff in army.effects_to_activate_next_round
    )
