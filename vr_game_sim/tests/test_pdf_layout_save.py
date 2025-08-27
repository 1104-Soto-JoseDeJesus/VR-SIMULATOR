import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from PyQt6 import QtWidgets
from vr_game_sim import gui_main


def test_pdf_layout_persistence(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_func = gui_main.get_pdf_layout_path
    gui_main.get_pdf_layout_path = lambda: str(tmp_path / "pdf_layout.json")
    try:
        main = gui_main.MainWindow()
        dlg = gui_main.PDFLayoutDialog(main)
        page = dlg._page_widgets[0]
        page.add_item("army_composition", 10, 20, scale=1.5)
        page.add_item("army_composition", 30, 40)
        dlg._save_layout()
        data = json.load(open(tmp_path / "pdf_layout.json"))
        items = data["pages"][0]["items"]
        coords = {(int(it["x"]), int(it["y"])) for it in items}
        assert coords == {(10, 20), (30, 40)}
        scaled = next(it for it in items if int(it["x"]) == 10 and int(it["y"]) == 20)
        assert scaled.get("scale") == 1.5
        # confirm loader reads it back
        pages = gui_main.load_pdf_layout()
        coords = {(int(it["x"]), int(it["y"])) for it in pages[0]["items"]}
        assert (30, 40) in coords
        loaded = next(it for it in pages[0]["items"] if int(it["x"]) == 10 and int(it["y"]) == 20)
        assert loaded.get("scale") == 1.5
    finally:
        gui_main.get_pdf_layout_path = original_func
