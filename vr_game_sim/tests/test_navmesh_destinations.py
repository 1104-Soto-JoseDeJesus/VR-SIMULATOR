import os
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_path_between_uses_true_destination():
    app = _get_app()
    from vr_game_sim.gui_main import BattlefieldTab

    tab = BattlefieldTab()
    tab._timer.stop()

    start = (5.0, 5.0)
    end = (45.0, 55.0)

    path = tab._path_between(start, end)
    assert path
    assert path[-1] == end
