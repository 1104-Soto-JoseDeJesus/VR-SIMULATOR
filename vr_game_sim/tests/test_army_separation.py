import math

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator


def test_engaged_armies_maintain_min_spacing():
    """Armies should be kept apart by at least the simulator's spacing."""
    unit = Unit("infantry", 5, initial_count=10)
    a1 = Army("A", unit)
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
