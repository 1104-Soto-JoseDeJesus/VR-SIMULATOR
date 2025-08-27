from pathlib import Path

from vr_game_sim.navmesh import NavMesh


def test_navmesh_pathfinding():
    nav = NavMesh.from_json(Path(__file__).resolve().parent.parent / 'navmesh_sample.json')
    path = nav.find_path((10, 10), (150, 150))
    assert path[0] == (10, 10)
    assert path[-1] == (150, 150)
    assert len(path) == 3
    assert path[1] == (150.0, 50.0)
