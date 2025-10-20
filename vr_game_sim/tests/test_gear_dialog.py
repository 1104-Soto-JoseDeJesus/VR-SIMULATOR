import os

import pytest

try:  # pragma: no cover - exercised in CI when PyQt is present
    from PyQt6 import QtWidgets
except ImportError:  # pragma: no cover - gracefully skip when Qt is unavailable
    pytest.skip("PyQt6 not available", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from vr_game_sim.gui_main import GearSelectionDialog, MainWindow


def _get_app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_gear_button_enabled():
    _get_app()
    window = MainWindow()
    try:
        assert window.army1_frame.gear_btn.isEnabled()
        assert window.army2_frame.gear_btn.isEnabled()
    finally:
        window.close()


def test_gear_selection_persists_to_config(monkeypatch):
    _get_app()
    window = MainWindow()
    try:
        frame = window.army1_frame
        frame.hero1_combo.setCurrentText("Leif")
        frame.hero2_combo.setCurrentText("Laird")

        chosen_weapon = "gear_immolated_axe_legendary"
        chosen_head = "gear_blazing_helmet_epic"

        def _auto_accept(self: GearSelectionDialog) -> QtWidgets.QDialog.DialogCode:
            weapon_combo = self._slot_boxes[(1, "weapon")]
            weapon_idx = weapon_combo.findData(chosen_weapon)
            assert weapon_idx >= 0
            weapon_combo.setCurrentIndex(weapon_idx)

            head_combo = self._slot_boxes[(2, "head")]
            head_idx = head_combo.findData(chosen_head)
            assert head_idx >= 0
            head_combo.setCurrentIndex(head_idx)

            self.accept()
            return QtWidgets.QDialog.DialogCode.Accepted

        monkeypatch.setattr(GearSelectionDialog, "exec", _auto_accept, raising=False)

        window._open_gear_dialog(frame)

        gear_config = frame.get_gear_config()
        assert gear_config[1]["weapon"] == chosen_weapon
        assert gear_config[2]["head"] == chosen_head

        assert frame.gear_btn.text().startswith("Gear (")

        army_cfg = frame.build_config()
        assert army_cfg["heroes"][0]["gear_ids"]["weapon"] == chosen_weapon
        assert army_cfg["heroes"][1]["gear_ids"]["head"] == chosen_head
    finally:
        window.close()
