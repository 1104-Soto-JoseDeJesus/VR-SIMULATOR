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
    engage_dist = 2 * speed * 2 + ENGAGEMENT_DISTANCE - 70
    back_dist = speed * 3 * 0.7
    lateral = engage_dist * 0.6

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    # horizontal distance between opposing front slots
    assert dist(coords1[1], coords2[1]) == pytest.approx(engage_dist)
    # horizontal distance between front and back slots of same team
    assert dist(coords1[1], coords1[5]) == pytest.approx(back_dist)
    # vertical distance between columns
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


def test_four_column_pairing_and_fallback():
    engine = ArenaEngine()

    a0f = make_army("A0F")
    a0b = make_army("A0B")
    a1f = make_army("A1F")
    a1b = make_army("A1B")
    a2b = make_army("A2B")
    a3f = make_army("A3F")
    a3b = make_army("A3B")

    b0f = make_army("B0F")
    b0b = make_army("B0B")
    b1f = make_army("B1F")
    b2f = make_army("B2F")
    b2b = make_army("B2B")

    r_front_y = 0.0
    r_back_y = -ENGAGEMENT_DISTANCE * 2
    b_front_y = ENGAGEMENT_DISTANCE * 2
    b_back_y = ENGAGEMENT_DISTANCE * 4

    layout = {
        "red": [
            {"army": a0f, "position": (0.0, r_front_y), "index": 0},
            {"army": a0b, "position": (0.0, r_back_y), "index": 4},
            {"army": a1f, "position": (300.0, r_front_y), "index": 1},
            {"army": a1b, "position": (300.0, r_back_y), "index": 5},
            {"army": a2b, "position": (600.0, r_back_y), "index": 6},
            {"army": a3f, "position": (900.0, r_front_y), "index": 3},
            {"army": a3b, "position": (900.0, r_back_y), "index": 7},
        ],
        "blue": [
            {"army": b0f, "position": (0.0, b_front_y), "index": 0},
            {"army": b0b, "position": (0.0, b_back_y), "index": 4},
            {"army": b1f, "position": (300.0, b_front_y), "index": 1},
            {"army": b2f, "position": (600.0, b_front_y), "index": 2},
            {"army": b2b, "position": (600.0, b_back_y), "index": 6},
        ],
    }

    engine.start_arena_battle(layout)

    # Column 0: full pairing
    assert engine._armies[a0f.name].direct_target == b0f.name
    assert engine._armies[a0b.name].direct_target == b0f.name
    assert engine._armies[b0f.name].direct_target == a0f.name
    assert engine._armies[b0b.name].direct_target == a0f.name

    # Column 1: red back falls back to blue front
    assert engine._armies[a1f.name].direct_target == b1f.name
    assert engine._armies[a1b.name].direct_target == b1f.name
    assert engine._armies[b1f.name].direct_target == a1f.name

    # Column 2: blue front falls back to red back
    assert engine._armies[a2b.name].direct_target == b2f.name
    assert engine._armies[b2b.name].direct_target == a2b.name
    assert engine._armies[b2f.name].direct_target == a2b.name

    # Column 3: no blue armies -> red units retarget to nearest enemy (column 2 front)
    assert engine._armies[a3f.name].direct_target == b2f.name
    assert engine._armies[a3b.name].direct_target == b2f.name
