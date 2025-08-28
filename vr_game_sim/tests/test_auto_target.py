import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_defender_auto_targets_attacker():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red')
    engine.add_army(army_b, 'blue')

    engine.engage('A', 'B')

    # Defender should automatically target the attacker
    assert engine._armies['B'].direct_target == 'A'
    # Both directions should be scheduled
    assert ('A', 'B') in engine._pending_engagements
    assert ('B', 'A') in engine._pending_engagements

    # After one second both engagements should be active
    engine.tick(1.0)
    assert ('A', 'B') in engine._engagements
    assert ('B', 'A') in engine._engagements
