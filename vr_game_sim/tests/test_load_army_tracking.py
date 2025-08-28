import os
import json
from PyQt6 import QtWidgets
import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.main import get_setup_data_for_saving


def test_load_army_adds_icon(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    # Prepare simple army configuration and save to file
    army = Army('A', Unit('pikemen', 5, initial_count=10))
    cfg = get_setup_data_for_saving([army])[0]
    cfg['speed'] = 1.0
    file_path = tmp_path / 'army.json'
    with open(file_path, 'w', encoding='utf-8') as fh:
        json.dump(cfg, fh)

    # Patch the file dialog to return our saved army
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', lambda *a, **k: (str(file_path), ''))

    from vr_game_sim.gui_main import BattlefieldTab

    tab = BattlefieldTab()
    tab._load_army()
    tab._timer.stop()

    assert 'A' in tab._icons
