import math

from vr_game_sim.movement_controller import MovementController, NavMesh


def build_basic_navmesh():
    mesh = NavMesh()
    mesh.add_node("A", (0.0, 0.0))
    mesh.add_node("B", (10.0, 0.0))
    mesh.add_node("C", (10.0, 10.0))
    mesh.add_edge("A", "B")
    mesh.add_edge("B", "C")
    return mesh


def test_army_moves_along_path():
    mesh = build_basic_navmesh()
    mc = MovementController(mesh)
    mc.register_army("army", (0.0, 0.0), speed=10.0)
    mc.set_waypoint("army", (10.0, 10.0))

    # Path length is 20 units; at 10u/s this takes 2 seconds => 2000 ticks
    for _ in range(2000):
        mc.tick()

    x, y = mc.get_position("army")
    assert math.isclose(x, 10.0, abs_tol=1e-3)
    assert math.isclose(y, 10.0, abs_tol=1e-3)


def test_snap_to_target():
    mesh = NavMesh()
    mesh.add_node("A", (0.0, 0.0))
    mesh.add_node("B", (10.0, 0.0))
    mesh.add_edge("A", "B")

    mc = MovementController(mesh)
    mc.register_army("army", (0.0, 0.0), speed=10.0)
    mc.snap_to_target("army", (10.0, 0.0), attack_range=2.0)

    # Should travel 8 units => 800 ticks
    for _ in range(800):
        mc.tick()

    x, y = mc.get_position("army")
    assert math.isclose(x, 8.0, abs_tol=1e-3)
    assert math.isclose(y, 0.0, abs_tol=1e-3)
