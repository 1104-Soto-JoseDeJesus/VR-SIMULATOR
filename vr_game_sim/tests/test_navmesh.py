from vr_game_sim.navmesh import NavMesh, Polygon

def test_navmesh_path():
    nm = NavMesh([Polygon(vertices=[(0, 0), (10, 0), (10, 10), (0, 10)], neighbors=[])])
    path = nm.find_path((1, 1), (9, 9))
    assert path[0] == (1, 1)
    assert path[-1] == (9, 9)
    assert len(path) == 2
