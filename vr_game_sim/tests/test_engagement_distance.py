import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_long_distance_march_delays_engagement():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', position=(0, 0), speed=1)
    engine.add_army(army_b, 'blue', position=(5, 0), speed=0)

    engine.engage('A', 'B')
    assert ('A', 'B') in engine._pending_engagements

    engine.tick(1.0)
    assert ('A', 'B') not in engine._engagements
    assert ('A', 'B') in engine._pending_engagements

    engine.tick(1.0)
    assert ('A', 'B') not in engine._engagements
    assert ('A', 'B') in engine._pending_engagements

    engine.tick(1.0)
    assert ('A', 'B') not in engine._engagements
    assert ('A', 'B') in engine._pending_engagements

    engine.tick(1.0)
    assert ('A', 'B') in engine._engagements


def test_mutual_approach_engages_when_close():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', position=(0, 0), speed=1)
    engine.add_army(army_b, 'blue', position=(10, 0), speed=1)

    engine.engage('A', 'B')
    engine.engage('B', 'A')
    assert ('A', 'B') in engine._pending_engagements
    assert ('B', 'A') in engine._pending_engagements

    for _ in range(4):
        engine.tick(1.0)
        assert ('A', 'B') not in engine._engagements
        assert ('B', 'A') not in engine._engagements
        assert ('A', 'B') in engine._pending_engagements
        assert ('B', 'A') in engine._pending_engagements

    engine.tick(1.0)
    assert ('A', 'B') in engine._engagements
    assert ('B', 'A') in engine._engagements
