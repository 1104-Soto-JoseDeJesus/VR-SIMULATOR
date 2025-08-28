from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_round_report_includes_troop_counts():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)
    atk = Army('A', Unit('archers', 5, initial_count=100))
    dfd = Army('B', Unit('pikemen', 5, initial_count=100))
    engine.add_army(atk, 'red')
    engine.add_army(dfd, 'blue')
    engine.engage('A', 'B')
    engine.tick(1.1)
    rounds = builder.get_rounds()[('A', 'B')]
    assert any('Troops:' in line for line in rounds[0]['active_effects'])

