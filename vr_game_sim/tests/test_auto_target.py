import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_defender_auto_targets_attacker_when_idle():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red')
    engine.add_army(army_b, 'blue')

    engine.engage('A', 'B')

    # Defender should immediately target the attacker
    assert engine._armies['B'].direct_target == 'A'
    # Both engagements should be scheduled
    assert ('A', 'B') in engine._pending_engagements
    assert ('B', 'A') in engine._pending_engagements

    engine.tick(1.0)
    # After one second both engagements are active
    assert ('A', 'B') in engine._engagements
    assert ('B', 'A') in engine._engagements


def test_defender_with_existing_target_does_not_auto_target():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    army_c = make_army('C')
    engine.add_army(army_a, 'red')
    engine.add_army(army_b, 'blue')
    engine.add_army(army_c, 'red')

    engine.engage('B', 'C')  # B already targets C
    engine.engage('A', 'B')  # A attacks B

    # B should continue targeting C
    assert engine._armies['B'].direct_target == 'C'
    # No engagement from B to A should be scheduled
    assert ('B', 'A') not in engine._pending_engagements

    engine.tick(1.0)
    # After one second B still does not engage A
    assert ('B', 'A') not in engine._engagements
    assert ('A', 'B') in engine._engagements
    assert ('B', 'C') in engine._engagements
