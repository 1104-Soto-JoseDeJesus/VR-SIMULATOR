import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets

import uuid

from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.gui_main import MainWindow
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, DoTType

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


def test_builder_records_defender_global_rounds():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)
    atk_a = make_army("A")
    atk_c = make_army("C")
    dfd_b = make_army("B")
    engine.add_army(atk_a, "red")
    engine.add_army(atk_c, "red")
    engine.add_army(dfd_b, "blue")
    engine.tick(0.3)
    engine.engage("A", "B")
    engine.tick(0.7)  # start A-B at t=1
    engine.tick(0.1)
    engine.engage("C", "B")
    engine.tick(0.9)  # t=2, round2 for A-B and round1 for C-B
    rounds = builder.get_rounds()
    assert rounds[("A", "B")][0]["defender_global_round"] == 1
    assert rounds[("A", "B")][1]["defender_global_round"] == 2
    assert rounds[("C", "B")][0]["defender_global_round"] == 2


def test_gui_displays_global_and_local_rounds():
    window = MainWindow()
    rb = window.battlefield_tab.report_builder
    b = rb.get_builder("A", "B")
    b.emit_round(1, [], {"A": [], "B": []})
    rb.record_defender_round("A", "B", 1, 5)
    window.update_battlefield_reports()
    item = window.bf_report_list.item(0)
    window.bf_report_list.setCurrentItem(item)
    text = window.bf_output_text.toPlainText()
    assert "Round 1 (Defender Round 5)" in text
    top = window.bf_output_tree.topLevelItem(0)
    assert top.text(0) == "Round 1 (Defender Round 5)"
    window.close()


def test_dot_effects_logged_in_reports():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)
    atk = make_army("A")
    dfd = make_army("B")
    engine.add_army(atk, "red", position=(0, 0), speed=0)
    engine.add_army(dfd, "blue", position=(2, 0), speed=0)

    dot = EffectInstance(
        id=uuid.uuid4(),
        source_skill_id="test",
        effect_type=EffectType.DAMAGE_OVER_TIME,
        duration=1,
        config={"dot_type": DoTType.BLEED, "status_effect_factor": 100},
    )
    dfd.active_effects.append(dot)

    engine.engage("A", "B")
    engine.tick(1.0)

    rounds = builder.get_rounds()[("A", "B")]
    effects = rounds[0]["active_effects"]
    assert any("Damage Over Time" in e for e in effects)

    report_text = builder.get_reports()[("A", "B")]
    assert "Damage Over Time" in report_text
