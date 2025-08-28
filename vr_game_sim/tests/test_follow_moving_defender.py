import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_attackers_follow_moving_defenders():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    army_c = make_army('C')

    engine.add_army(army_a, 'red', position=(0, 0), speed=2)
    engine.add_army(army_b, 'blue', position=(10, 0), speed=1)
    engine.add_army(army_c, 'red', position=(20, 0), speed=0)

    engine.set_direct_target('B', 'C')
    engine.set_direct_target('A', 'B')

    engine.tick(1.0)
    b_pos1 = engine._armies['B'].position
    path_a1 = engine._armies['A'].path
    assert len(path_a1) == 1
    assert path_a1[0][0] == pytest.approx(b_pos1[0] - 2, abs=1e-3)
    assert path_a1[0][1] == pytest.approx(b_pos1[1], abs=1e-3)

    engine.tick(1.0)
    b_pos2 = engine._armies['B'].position
    path_a2 = engine._armies['A'].path
    assert len(path_a2) == 1
    assert path_a2[0][0] == pytest.approx(b_pos2[0] - 2, abs=1e-3)
    assert path_a2[0][1] == pytest.approx(b_pos2[1], abs=1e-3)
    assert path_a2 != path_a1
