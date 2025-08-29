import pytest

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_defender_targets_attacker_on_first_engagement():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', position=(0, 0), speed=1)
    engine.add_army(
        army_b, 'blue', position=(ENGAGEMENT_DISTANCE + 2, 0), speed=1
    )

    engine.engage('A', 'B')
    # Defender should remain idle without a target until combat begins
    assert engine._armies['B'].direct_target is None
    assert engine._armies['B'].path == []
    assert ('A', 'B') in engine._pending_engagements
    assert ('B', 'A') not in engine._pending_engagements

    engine.tick(0.5)
    # Still waiting for attacker to arrive
    assert engine._armies['B'].direct_target is None
    assert engine._armies['B'].position == (ENGAGEMENT_DISTANCE + 2, 0.0)

    engine.tick(2.5)
    # After attacker moves into range defender targets the attacker
    assert engine._armies['B'].direct_target == 'A'
    assert engine._armies['B'].position == (ENGAGEMENT_DISTANCE + 2, 0.0)
    expected = (ENGAGEMENT_DISTANCE + 2) - ENGAGEMENT_DISTANCE
    assert engine._armies['A'].position[0] == pytest.approx(expected, abs=1e-3)


def test_first_arrival_becomes_direct_target():
    engine = BattlefieldEngine()
    fast = make_army('F')
    slow = make_army('S')
    defender = make_army('D')
    engine.add_army(fast, 'red', position=(0, 0), speed=3)
    engine.add_army(
        slow, 'red', position=(2 * ENGAGEMENT_DISTANCE + 6, 0), speed=1
    )
    engine.add_army(defender, 'blue', position=(ENGAGEMENT_DISTANCE + 2, 0), speed=0)

    engine.engage('S', 'D')  # Slow engages first
    engine.engage('F', 'D')  # Fast engages second but will arrive first

    engine.tick(1.0)
    # Fast army should be the defender's target after first round
    assert engine._armies['D'].direct_target == 'F'

    engine.tick(4.0)
    # Slow army eventually engages but defender keeps targeting fast army
    assert ('S', 'D') in engine._engagements
    assert engine._armies['D'].direct_target == 'F'


def test_defender_with_existing_target_does_not_auto_target():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    army_c = make_army('C')
    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)
    engine.add_army(army_c, 'red', speed=0)

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
