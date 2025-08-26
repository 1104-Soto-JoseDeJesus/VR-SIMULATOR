import math

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator


def test_engaged_armies_maintain_min_spacing():
    """Armies should be kept apart by at least the simulator's spacing."""
    unit = Unit("infantry", 5, initial_count=10)
    a1 = Army("A", unit, movement_speed=5.0)
    a2 = Army("B", unit)
    a1.team = 0
    a2.team = 1
    bf = Battlefield(10, 10)
    bf.place_army(a1, 5.0, 5.0)
    bf.place_army(a2, 5.0, 5.0)
    sim = MultiArmySimulator(bf, [a1, a2], min_spacing=2.0)

    # Initial step should separate and start the duel
    sim.step(0.01)
    dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
    assert dist >= 2.0

    # Force overlap and ensure the spacing is enforced each tick
    for _ in range(3):
        bf.place_army(a1, a2.float_x, a2.float_y)
        sim.step(0.01)
        dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
        assert dist >= 2.0


def test_marching_army_stops_before_overlap():
    """An advancing army should halt at the minimum spacing when engaging."""
    unit = Unit("infantry", 5, initial_count=10)
    a1 = Army("A", unit, movement_speed=5.0)
    a2 = Army("B", unit)
    a1.team = 0
    a2.team = 1
    bf = Battlefield(20, 5)
    bf.place_army(a1, 0.0, 0.0)
    bf.place_army(a2, 5.0, 0.0)
    sim = MultiArmySimulator(bf, [a1, a2], min_spacing=2.0)

    a1.set_destination((a2.float_x, a2.float_y))
    sim.step(1.0)

    # Army a1 should stop 2 units away from a2 and a duel should start
    assert math.isclose(a1.float_x, 3.0)
    assert math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y) >= 2.0
    assert a2.float_x == 5.0
    assert len(sim.active_duels) == 1
