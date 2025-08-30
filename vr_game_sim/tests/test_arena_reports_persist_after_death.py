from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder


def make_army(name: str, count: int) -> Army:
    unit = Unit('pikemen', 5, initial_count=count)
    return Army(name, unit)


def test_reports_persist_after_army_death():
    builder = BattlefieldReportBuilder()
    # Seed the builder with a report for A vs B
    b = builder.get_builder('A', 'B')
    b.emit_round(1, [], {'A': [], 'B': []})

    engine = BattlefieldEngine(report_builder=builder)
    army_a = make_army('A', 100)
    army_b = make_army('B', 1)
    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)
    engine.engage('A', 'B')
    engine.tick(1.0)
    assert 'B' not in engine._armies
    assert ('A', 'B') in builder.get_reports()
    builder.clear_all()
    assert builder.get_reports() == {}
