import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str, count: int) -> Army:
    unit = Unit('pikemen', 5, initial_count=count)
    return Army(name, unit)


def test_defeated_army_cleanup_removes_references():
    engine = BattlefieldEngine()
    army_a = make_army('A', 100)
    army_b = make_army('B', 1)
    army_c = make_army('C', 100)

    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)
    engine.add_army(army_c, 'red', position=(5, 0), speed=1)

    engine.set_direct_target('A', 'B')
    engine.set_direct_target('C', 'B')

    engine.tick(1.0)

    assert 'B' not in engine._armies
    assert 'B' not in engine._graph
    assert all('B' not in neighbours for neighbours in engine._graph.values())
    assert all('B' not in pair for pair in engine._pending_engagements)

    c_ctx = engine._armies['C']
    assert c_ctx.direct_target is None
    assert not c_ctx.pursue_target
    assert c_ctx.path == []
