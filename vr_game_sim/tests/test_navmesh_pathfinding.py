from pytest import approx

from vr_game_sim.navmesh import NavMesh
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def test_navmesh_astar_avoids_obstacles():
    grid = [
        "...",
        ".#.",
        "...",
    ]
    mesh = NavMesh.from_grid(grid)
    path = mesh.astar((0, 0), (2, 2))
    assert path[0] == (0, 0) and path[-1] == (2, 2)
    assert (1, 1) not in path  # obstacle should be avoided
    # consecutive steps must be adjacent
    for a, b in zip(path, path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def test_battlefield_path_and_snap_to_enemy():
    unit_a = Unit('pikemen', 5, initial_count=10)
    unit_b = Unit('archers', 5, initial_count=10)
    army_a = Army('A1', unit_a)
    army_b = Army('A2', unit_b)

    engine = BattlefieldEngine()
    engine.add_army(army_a, 'red', position=(0.0, 0.0), speed=3.0)
    engine.add_army(army_b, 'blue', position=(5.0, 0.0), speed=0.0)
    engine.engage('A1', 'A2')

    engine.set_path('A1', [(5.0, 0.0)])
    engine.tick(1.1)  # slightly more than one second to cross snap threshold

    assert engine._armies['A1'].position == (approx(5.0), approx(0.0))
    assert engine._armies['A1'].path == []


def test_battlefield_follow_multiple_waypoints():
    unit = Unit('pikemen', 5, initial_count=10)
    army = Army('A', unit)
    engine = BattlefieldEngine()
    engine.add_army(army, 'red', position=(0.0, 0.0), speed=1.0)
    engine.set_path('A', [(1.0, 0.0), (1.0, 1.0)])
    engine.tick(2.1)  # traverse both segments with some slack
    assert engine._armies['A'].position == (approx(1.0, abs=1e-3), approx(1.0, abs=1e-3))
    assert engine._armies['A'].path == []
