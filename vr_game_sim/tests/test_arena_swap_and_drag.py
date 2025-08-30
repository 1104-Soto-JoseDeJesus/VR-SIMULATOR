import os
from types import SimpleNamespace
from PyQt6 import QtWidgets, QtCore


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _make_dialog_sequence(configs):
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

    return DummyDialog


def _basic_cfg(name: str) -> dict:
    return {
        "army_name": name,
        "unit_type": "archers",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }


def test_swap_teams(monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    configs = [_basic_cfg("A"), _basic_cfg("B")]
    monkeypatch.setattr(
        "vr_game_sim.gui_main.ArmySetupDialog", _make_dialog_sequence(configs)
    )

    tab = ArenaTab()
    tab._slot_clicked("team1", 0)
    tab._slot_clicked("team2", 0)

    pos_a_before = tab._icons["A"].pos()
    pos_b_before = tab._icons["B"].pos()

    tab._swap_teams()

    assert tab._slot_army[("team1", 0)]["army"].name == "B"
    assert tab._slot_army[("team2", 0)]["army"].name == "A"
    assert tab._slot_army[("team1", 0)]["team"] == "red"
    assert tab._slot_army[("team2", 0)]["team"] == "blue"
    assert tab._icons["A"].pos() == pos_b_before
    assert tab._icons["B"].pos() == pos_a_before


def test_drag_moves_army(monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    configs = [_basic_cfg("A")]
    monkeypatch.setattr(
        "vr_game_sim.gui_main.ArmySetupDialog", _make_dialog_sequence(configs)
    )

    tab = ArenaTab()
    tab._slot_clicked("team1", 0)
    info_before = tab._slot_army[("team1", 0)]

    target_pos = tab._slot_items[("team2", 0)].scenePos()
    tab._on_icon_drop("A", target_pos)

    assert tab._slot_army[("team1", 0)] is None
    moved = tab._slot_army[("team2", 0)]
    assert moved["army"] is info_before["army"]
    assert moved["team"] == "blue"
    assert moved["config"]["team"] == "blue"
    expected = QtCore.QPointF(*tab.slot_coords["team2"][0])
    assert tab._icons["A"].pos() == expected
