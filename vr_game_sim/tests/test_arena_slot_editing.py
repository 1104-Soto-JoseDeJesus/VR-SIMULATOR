import os
from types import SimpleNamespace
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_editing_existing_slot(monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    # Two sequential configurations for creating then editing an army.
    cfg_initial = {
        "army_name": "Alpha",
        "unit_type": "archers",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }
    cfg_updated = dict(cfg_initial, army_name="Beta")

    configs = [cfg_initial, cfg_updated]

    def DummyDialog(parent=None):
        cfg = configs.pop(0)

        class _D:
            def __init__(self, cfg):
                self._cfg = cfg
                self.frame = SimpleNamespace(populate_from_config=lambda c: None)
                self.team_combo = SimpleNamespace(setCurrentText=lambda t: None)
                self.speed_spin = SimpleNamespace(setValue=lambda v: None)

            def exec(self):
                return int(QtWidgets.QDialog.DialogCode.Accepted)

            def get_config(self):
                return self._cfg

        return _D(cfg)

    monkeypatch.setattr("vr_game_sim.gui_main.ArmySetupDialog", DummyDialog)

    tab = ArenaTab()
    tab._slot_clicked("team1", 0)  # place initial army
    assert tab._slot_army[("team1", 0)]["army"].name == "Alpha"

    tab._slot_clicked("team1", 0)  # edit existing army
    assert tab._slot_army[("team1", 0)]["army"].name == "Beta"
    assert "Alpha" not in tab._icons
    assert "Beta" in tab._icons


def test_editing_existing_slot_via_icon(monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab, QtCore

    cfg_initial = {
        "army_name": "Alpha",
        "unit_type": "archers",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }
    cfg_updated = dict(cfg_initial, army_name="Beta")

    configs = [cfg_initial, cfg_updated]

    def DummyDialog(parent=None):
        cfg = configs.pop(0)

        class _D:
            def __init__(self, cfg):
                self._cfg = cfg
                self.frame = SimpleNamespace(populate_from_config=lambda c: None)
                self.team_combo = SimpleNamespace(setCurrentText=lambda t: None)
                self.speed_spin = SimpleNamespace(setValue=lambda v: None)

            def exec(self):
                return int(QtWidgets.QDialog.DialogCode.Accepted)

            def get_config(self):
                return self._cfg

        return _D(cfg)

    monkeypatch.setattr("vr_game_sim.gui_main.ArmySetupDialog", DummyDialog)

    tab = ArenaTab()
    tab._slot_clicked("team1", 0)
    assert tab._slot_army[("team1", 0)]["army"].name == "Alpha"

    icon = tab._icons["Alpha"]

    class DummyEvent:
        def button(self):
            return QtCore.Qt.MouseButton.LeftButton

        def accept(self):
            pass

    icon.mouseDoubleClickEvent(DummyEvent())

    assert tab._slot_army[("team1", 0)]["army"].name == "Beta"
    assert "Alpha" not in tab._icons
    assert "Beta" in tab._icons
