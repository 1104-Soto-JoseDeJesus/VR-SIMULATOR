import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from PyQt6 import QtWidgets
from vr_game_sim import gui_main


def test_pdf_layout_persistence(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_file = gui_main.__file__
    gui_main.__file__ = str(tmp_path / "dummy.py")
    try:
        dlg = gui_main.PDFLayoutDialog()
        dlg._count_spin.setValue(2)
        # adjust first page summary only, second page composition only
        first_checks = dlg._page_checks[0]
        first_checks["summary"].setChecked(True)
        first_checks["army_composition"].setChecked(False)
        second_checks = dlg._page_checks[1]
        second_checks["summary"].setChecked(False)
        second_checks["army_composition"].setChecked(True)
        dlg._save_layout()
        data = json.load(open(tmp_path / "pdf_layout.json"))
        assert data["pages"] == [["summary"], ["army_composition"]]
        # confirm loader reads it back
        pages = gui_main.load_pdf_layout()
        assert pages == [["summary"], ["army_composition"]]
    finally:
        gui_main.__file__ = original_file
