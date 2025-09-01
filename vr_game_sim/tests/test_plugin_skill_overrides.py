from vr_game_sim.main import create_armies_from_data
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.constants import (
    EFFECT_NAME_SHIELD_REFLECTOR_BUFF,
    EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
)


def _basic_army_config(plugin_id, overrides):
    return {
        "army_name": "OverrideArmy",
        "unit_type": "archers",
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
                "plugin_skill_ids": [plugin_id],
                "skill_overrides": {plugin_id: overrides},
            }
        ],
        "team": "red",
        "speed": 50.0,
    }


def test_shield_reflector_counterattack_override():
    boost = 1.8
    cfg = _basic_army_config(
        "plugin_shield_reflector", {"config": {"counterattack_boost": boost}}
    )
    army = create_armies_from_data([cfg])[0]
    enemy = Army("E", Unit("pikemen", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill = [s for s in army.heroes[0].skills if s["id"] == "plugin_shield_reflector"][0]
    army.started_last_round_with_active_shield = True
    happened, _ = skill["logic_handler"](army, enemy, skill, None, sim)
    army.activate_queued_effects()
    assert happened
    buff = next(e for e in army.active_effects if e.name == EFFECT_NAME_SHIELD_REFLECTOR_BUFF)
    assert buff.magnitude == boost


def test_first_strike_rage_override():
    rage = 150
    cfg = _basic_army_config(
        "plugin_first_strike", {"config": {"rage_per_round": rage}}
    )
    army = create_armies_from_data([cfg])[0]
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    sim.round = 1
    skill = [s for s in army.heroes[0].skills if s["id"] == "plugin_first_strike"][0]
    happened, _ = skill["logic_handler"](army, enemy, skill, None, sim)
    army.activate_queued_effects()
    assert happened
    effect = next(e for e in army.active_effects if e.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA)
    assert effect.config.get("rage_per_round") == rage
