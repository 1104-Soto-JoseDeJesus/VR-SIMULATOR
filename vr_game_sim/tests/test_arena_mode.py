import os
import pytest
from PyQt6 import QtWidgets

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.battlefield_engine import ENGAGEMENT_DISTANCE


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_army(name: str, count: int = 1000) -> Army:
    unit = Unit("pikemen", 5, initial_count=count)
    return Army(name, unit)


def test_slot_distances():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab()
    coords1 = tab.slot_coords["team1"]
    coords2 = tab.slot_coords["team2"]

    speed = 50.0
    base_dist = 2 * speed * 2
    lateral = base_dist

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    # vertical distance between opposing front slots
    assert dist(coords1[1], coords2[1]) == pytest.approx(base_dist)
    # vertical distance between front and back slots of same team
    assert dist(coords1[1], coords1[5]) == pytest.approx(base_dist)
    # lateral distance between columns
    assert dist(coords1[0], coords1[1]) == pytest.approx(lateral)


def test_initial_column_targeting():
    engine = ArenaEngine()
    a_left = make_army("A_left")
    a_right = make_army("A_right")
    b_left = make_army("B_left")
    b_right = make_army("B_right")

    layout = {
        "red": [
            {"army": a_left, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_right, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b_left, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": b_right, "position": (300.0, 200.0), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    assert engine._armies[a_left.name].direct_target == b_left.name
    assert engine._armies[a_right.name].direct_target == b_right.name
    assert engine._armies[b_left.name].direct_target == a_left.name
    assert engine._armies[b_right.name].direct_target == a_right.name


def test_retarget_when_column_empty():
    engine = ArenaEngine()
    a_left = make_army("A_left")
    a_right = make_army("A_right")
    b_left = make_army("B_left", 1)  # dies quickly
    b_right = make_army("B_right")

    layout = {
        "red": [
            {"army": a_left, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_right, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b_left, "position": (0.0, ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 0},
            {"army": b_right, "position": (300.0, ENGAGEMENT_DISTANCE * 2), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(20):
        engine.tick(1.0)
        if "B_left" not in engine._armies:
            break

    assert "B_left" not in engine._armies
    assert engine._armies[a_left.name].direct_target == b_right.name


def test_defender_retarget_after_kill():
    engine = ArenaEngine()
    a1 = make_army("A1", 1)  # weak attacker
    a2 = make_army("A2")
    b1 = make_army("B1")

    layout = {
        "red": [
            {"army": a1, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a2, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b1, "position": (0.0, ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(20):
        engine.tick(1.0)
        if "A1" not in engine._armies:
            break

    assert "A1" not in engine._armies
    assert engine._armies[b1.name].direct_target == a2.name
