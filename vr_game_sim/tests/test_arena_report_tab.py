import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets

from vr_game_sim.gui_main import MainWindow

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_gui_lists_arena_reports():
    window = MainWindow()
    rb = window.arena_tab.report_builder
    b = rb.get_builder("A", "B")
    b.emit_round(1, [], {"A": [], "B": []})
    window.update_arena_reports()
    assert window.ar_report_list.count() == 1
    item = window.ar_report_list.item(0)
    window.ar_report_list.setCurrentItem(item)
    assert "Round 1" in window.ar_output_text.toPlainText()
    window.close()
