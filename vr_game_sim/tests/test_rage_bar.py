import os
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_rage_bar_updates_and_bounds():
    app = _get_app()
    from vr_game_sim.gui_main import ArmyIcon

    icon_path = os.path.join(os.path.dirname(__file__), "..", "Icons", "archers.png")
    icon = ArmyIcon(icon_path, None, 1.0)
    icon.set_rage(0.5)
    assert icon.rage_ratio == 0.5
    rect = icon.boundingRect()
    assert rect.top() < 0  # extra space for rage bar
