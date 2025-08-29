import os
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_slot_coordinates_symmetry():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab()

    scene = tab.view.sceneRect()
    cx = scene.width() / 2.0
    cy = scene.height() / 2.0
    speed = 50.0
    base_dist = 2 * speed * 2
    half = base_dist / 2.0

    left_outer = cx - 1.5 * base_dist
    left_inner = cx - 0.5 * base_dist
    right_inner = cx + 0.5 * base_dist
    right_outer = cx + 1.5 * base_dist

    expected_team1 = [
        (left_outer, cy - half),
        (left_inner, cy - half),
        (right_inner, cy - half),
        (right_outer, cy - half),
        (left_outer, cy - half - base_dist),
        (left_inner, cy - half - base_dist),
        (right_inner, cy - half - base_dist),
        (right_outer, cy - half - base_dist),
    ]
    expected_team2 = [
        (left_outer, cy + half),
        (left_inner, cy + half),
        (right_inner, cy + half),
        (right_outer, cy + half),
        (left_outer, cy + half + base_dist),
        (left_inner, cy + half + base_dist),
        (right_inner, cy + half + base_dist),
        (right_outer, cy + half + base_dist),
    ]

    assert tab.slot_coords["team1"] == expected_team1
    assert tab.slot_coords["team2"] == expected_team2
