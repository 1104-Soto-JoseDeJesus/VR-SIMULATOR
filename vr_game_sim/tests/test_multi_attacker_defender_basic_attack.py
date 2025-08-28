import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_defender_basic_attacks_only_direct_target():
    report_builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder)

    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(0, 0), speed=0)
    engine.add_army(atk2, 'red', position=(4, 0), speed=0)
    engine.add_army(dfd, 'blue', position=(2, 0), speed=0)

    engine.engage('A1', 'D')
    engine.engage('A2', 'D')

    engine.tick(1.0)

    rounds = report_builder.get_rounds()
    actions_a1 = rounds[('A1', 'D')][0]['combat_actions']
    actions_a2 = rounds[('A2', 'D')][0]['combat_actions']

    assert any(
        a['attacker_name'] == 'D' and a['action_type'] == 'Basic Attack'
        for a in actions_a1
    )
    assert not any(
        a['attacker_name'] == 'D' and a['action_type'] == 'Basic Attack'
        for a in actions_a2
    )
    assert any(
        a['attacker_name'] == 'D' and a['action_type'] == 'Counter Attack'
        for a in actions_a1
    )
    assert any(
        a['attacker_name'] == 'D' and a['action_type'] == 'Counter Attack'
        for a in actions_a2
    )
