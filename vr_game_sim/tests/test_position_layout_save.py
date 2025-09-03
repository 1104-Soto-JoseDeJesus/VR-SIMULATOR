import os
import json
from PyQt6 import QtWidgets


def _get_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_position_layout_save_and_load(tmp_path, monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab()
    tab._setups_dir = str(tmp_path)
    tab.formation_file = str(tmp_path / "formations.json")

    default_pos = tab.slot_coords["team1"][0]
    tab._toggle_position_layout(True)
    item = tab._slot_items[("team1", 0)]
    item.setPos(default_pos[0] + tab._cell_w * 0.7, default_pos[1] + tab._cell_h * 0.4)
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *args, **kwargs: ("test", True))
    tab._toggle_position_layout(False)

    with open(tab.formation_file, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert "test" in data
    saved = data["test"]["team1"][0]

    tab.slot_coords = tab._compute_slot_coords()
    tab._refresh_arena()
    tab._load_formation_layout("test")
    assert tab.slot_coords["team1"][0] == tuple(saved)
