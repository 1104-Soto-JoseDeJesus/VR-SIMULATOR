import math

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator


def test_armies_do_not_overlap_when_engaged():
    unit = Unit("infantry", 5, initial_count=10)
    a1 = Army("A", unit)
    a2 = Army("B", unit)
    a1.team = 0
    a2.team = 1
    bf = Battlefield(10, 10)
    bf.place_army(a1, 5.0, 5.0)
    bf.place_army(a2, 5.0, 5.0)
    sim = MultiArmySimulator(bf, [a1, a2])
    sim.step(0.01)
    dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
    assert dist >= 1.0
