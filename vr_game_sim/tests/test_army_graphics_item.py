import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets
from vr_game_sim.gui_main import ArmyGraphicsItem


def test_army_graphics_item_uses_placeholder(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    missing = tmp_path / "missing.png"
    item = ArmyGraphicsItem("Test", lambda *_: None, str(missing))
    assert item.main_pixmap.width() > 0
    assert item.main_pixmap.height() > 0
