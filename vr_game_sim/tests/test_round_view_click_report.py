import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets, QtCore, QtTest

from vr_game_sim.gui_main import MainWindow

# Ensure a single QApplication instance
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_click_round_item_no_crash():
    window = MainWindow()
    rounds = [
        {
            "round": 1,
            "combat_actions": [],
            "skill_triggers": {},
            "active_effects": [],
            "round_summary": {
                "Army 1": {"end": 100, "delta": -10},
                "Army 2": {"end": 80, "delta": -20},
            },
        }
    ]
    window._populate_round_tree(rounds)
    window.show()
    app.processEvents()
    item = window.output_tree.topLevelItem(0)
    rect = window.output_tree.visualItemRect(item)
    QtTest.QTest.mouseClick(
        window.output_tree.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        rect.center(),
    )
    assert window.output_tree.currentItem() is item
    window.close()
