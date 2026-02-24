import pytest
import os

from vr_game_sim.army_composition import Army
from vr_game_sim.cooldown_persistence import (
    DEFAULT_RAGE_THRESHOLDS_BY_TYPE,
    load_cooldown_defaults,
    save_cooldown_defaults,
)
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def _make_army(name: str, unit_type: str) -> Army:
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    return Army(name, Unit(unit_type, 5, initial_count=10), heroes=[hero])


def _get_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6 import QtWidgets
    except ImportError as exc:
        pytest.skip(f"PyQt6 unavailable in test environment: {exc}")

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_cooldown_defaults_persist_rage_thresholds_by_type(tmp_path):
    path = tmp_path / "cooldown_defaults.json"
    payload = {
        "rage_thresholds_by_type": {"archers": "950", "infantry": 1200},
        "skills": {"foo": True},
    }

    save_cooldown_defaults(payload, str(path))
    loaded = load_cooldown_defaults(str(path))

    assert loaded["rage_thresholds_by_type"] == {
        "infantry": 1200,
        "archers": 950,
        "pikemen": DEFAULT_RAGE_THRESHOLDS_BY_TYPE["pikemen"],
    }


def test_archers_custom_rage_threshold_overrides_default():
    army_archers = _make_army("Archers", "archers")
    army_enemy = Army("Enemy", Unit("pikemen", 5, initial_count=10), heroes=[])
    sim_archers = GameSimulator(
        army_archers,
        army_enemy,
        rage_thresholds_by_type={"archers": 950},
    )
    sim_archers.round = 1
    army_archers.army_round = 1
    army_archers.current_rage = 1000
    army_archers.hero1_rage_skill_queued_this_round = True
    sim_archers._execute_rage_skills(army_archers, army_enemy)
    assert army_archers.current_rage == 0

    army_infantry = _make_army("Infantry", "infantry")
    army_enemy2 = Army("Enemy2", Unit("pikemen", 5, initial_count=10), heroes=[])
    sim_infantry = GameSimulator(
        army_infantry,
        army_enemy2,
        rage_thresholds_by_type={"archers": 950},
    )
    sim_infantry.round = 1
    army_infantry.army_round = 1
    army_infantry.current_rage = 1000
    army_infantry.hero1_rage_skill_queued_this_round = True
    sim_infantry._execute_rage_skills(army_infantry, army_enemy2)
    assert army_infantry.current_rage == 1000
    assert not army_infantry.hero1_rage_skill_queued_this_round


def test_gui_debug_settings_include_rage_threshold_map():
    _get_app()
    from vr_game_sim.gui_main import MainWindow

    window = MainWindow()
    settings = window.get_simulator_debug_settings()

    assert "rage_thresholds_by_type" in settings
    assert settings["rage_thresholds_by_type"] == window.rage_thresholds_by_type
