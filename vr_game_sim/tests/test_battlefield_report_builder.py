import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets

from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.gui_main import MainWindow
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def test_builder_tracks_each_engagement():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)
    army_a = make_army("A")
    army_b = make_army("B")
    engine.add_army(army_a, "red")
    engine.add_army(army_b, "blue")
    engine.tick(0.3)
    engine.engage("A", "B")
    engine.tick(0.7)  # start engagement at t=1
    engine.tick(1.0)  # run one round
    reports = builder.get_reports()
    assert ("A", "B") in reports
    assert "Round 1" in reports[("A", "B")]


def test_gui_lists_battlefield_reports():
    window = MainWindow()
    rb = window.battlefield_tab.report_builder
    b = rb.get_builder("A", "B")
    b.emit_round(1, [], {"A": [], "B": []})
    window.update_battlefield_reports()
    assert window.bf_report_list.count() == 1
    item = window.bf_report_list.item(0)
    window.bf_report_list.setCurrentItem(item)
    assert "Round 1" in window.bf_output_text.toPlainText()
    window.close()
