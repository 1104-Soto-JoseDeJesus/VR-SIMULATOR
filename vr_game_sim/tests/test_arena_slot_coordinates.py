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
    engage_dist = 2 * speed * 2
    to_mid = engage_dist / 2.0
    back_offset = speed * 3

    top_outer = cy - 1.5 * engage_dist
    top_inner = cy - 0.5 * engage_dist
    bottom_inner = cy + 0.5 * engage_dist
    bottom_outer = cy + 1.5 * engage_dist

    front_x1 = cx - to_mid
    back_x1 = cx - to_mid - back_offset
    front_x2 = cx + to_mid
    back_x2 = cx + to_mid + back_offset

    expected_team1 = [
        (front_x1, top_outer),
        (front_x1, top_inner),
        (front_x1, bottom_inner),
        (front_x1, bottom_outer),
        (back_x1, top_outer),
        (back_x1, top_inner),
        (back_x1, bottom_inner),
        (back_x1, bottom_outer),
    ]
    expected_team2 = [
        (front_x2, top_outer),
        (front_x2, top_inner),
        (front_x2, bottom_inner),
        (front_x2, bottom_outer),
        (back_x2, top_outer),
        (back_x2, top_inner),
        (back_x2, bottom_inner),
        (back_x2, bottom_outer),
    ]

    assert tab.slot_coords["team1"] == expected_team1
    assert tab.slot_coords["team2"] == expected_team2
