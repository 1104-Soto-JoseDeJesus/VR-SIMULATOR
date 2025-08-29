from pytest import approx

from vr_game_sim.navmesh import NavMesh

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def test_navmesh_astar_ignores_obstacles():
    grid = [
        "...",
        ".#.",
        "...",
    ]
    mesh = NavMesh.from_grid(grid)
    path = mesh.astar((0, 0), (2, 2))
    assert path[0] == (0, 0) and path[-1] == (2, 2)
    # With diagonal movement allowed the shortest path uses straight diagonals
    assert len(path) == 3
    for a, b in zip(path, path[1:]):
        assert (abs(a[0] - b[0]), abs(a[1] - b[1])) in {(1, 1)}


def test_battlefield_path_stops_before_enemy():
    unit_a = Unit('pikemen', 5, initial_count=1000)
    unit_b = Unit('archers', 5, initial_count=1000)
    army_a = Army('A1', unit_a)
    army_b = Army('A2', unit_b)

    engine = BattlefieldEngine()
    engine.add_army(army_a, 'red', position=(0.0, 0.0), speed=3.0)
    engine.add_army(
        army_b, 'blue', position=(ENGAGEMENT_DISTANCE + 2, 0.0), speed=0.0
    )
    engine.engage('A1', 'A2')

    engine.tick(1.0)  # move for 1 second; engagement activates at the boundary
    engine.tick(0.1)  # ensure post-engagement updates run

    expected = (ENGAGEMENT_DISTANCE + 2) - ENGAGEMENT_DISTANCE
    assert engine._armies['A1'].position == (approx(expected), approx(0.0))
    assert engine._armies['A1'].path == []


def test_battlefield_repositions_when_too_close():
    unit_a = Unit('pikemen', 5, initial_count=10)
    unit_b = Unit('archers', 5, initial_count=10)
    army_a = Army('A1', unit_a)
    army_b = Army('A2', unit_b)

    engine = BattlefieldEngine()
    engine.add_army(
        army_a, 'red', position=(ENGAGEMENT_DISTANCE + 1.5, 0.0), speed=0.0
    )
    engine.add_army(
        army_b, 'blue', position=(ENGAGEMENT_DISTANCE + 2, 0.0), speed=0.0
    )
    engine.engage('A1', 'A2')

    engine.tick(0.1)  # reposition to maintain minimum distance

    expected = (ENGAGEMENT_DISTANCE + 2) - ENGAGEMENT_DISTANCE
    assert engine._armies['A1'].position == (approx(expected), approx(0.0))


def test_battlefield_follow_multiple_waypoints():
    unit = Unit('pikemen', 5, initial_count=10)
    army = Army('A', unit)
    engine = BattlefieldEngine()
    engine.add_army(army, 'red', position=(0.0, 0.0), speed=1.0)
    engine.set_path('A', [(1.0, 0.0), (1.0, 1.0)])
    engine.tick(2.1)  # traverse both segments with some slack
    assert engine._armies['A'].position == (approx(1.0, abs=1e-3), approx(1.0, abs=1e-3))
    assert engine._armies['A'].path == []


def test_navmesh_simplify_path_reduces_waypoints():
    grid = [
        "....",
        "....",
        "....",
        "....",
    ]
    mesh = NavMesh.from_grid(grid)
    raw = mesh.astar((0, 0), (3, 3))
    assert len(raw) > 2  # diagonal path includes intermediate cells
    simplified = mesh.simplify_path(raw)
    assert simplified == [(0, 0), (3, 3)]


def test_battlefield_takes_straight_route_without_obstacles():
    unit = Unit('pikemen', 5, initial_count=10)
    army = Army('A', unit)
    engine = BattlefieldEngine()
    engine.add_army(army, 'red', position=(0.0, 0.0), speed=1.0)

    grid = [
        "....",
        "....",
        "....",
        "....",
    ]
    mesh = NavMesh.from_grid(grid)
    cells = mesh.simplify_path(mesh.astar((0, 0), (3, 3)))
    path = [(float(x), float(y)) for x, y in cells[1:]]
    assert path == [(3.0, 3.0)]  # path reduced to destination only
    engine.set_path('A', path)
    engine.tick(5.0)  # plenty of time to reach destination
    assert engine._armies['A'].position == (approx(3.0, abs=1e-3), approx(3.0, abs=1e-3))
    assert engine._armies['A'].path == []
