import random

from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_attacker_and_defender_with_other_duels_can_engage():
    random.seed(0)
    battlefield = Battlefield(20, 20)
    # Create four armies
    # Use larger troop counts so duels persist long enough for secondary engagement
    a1 = Army("A1", Unit("infantry", 5, 100))
    a2 = Army("A2", Unit("infantry", 5, 100))
    d1 = Army("D1", Unit("archers", 5, 100))
    d2 = Army("D2", Unit("archers", 5, 100))

    a1.team = a2.team = 1
    d1.team = d2.team = 2

    # Initial positions
    battlefield.place_army(d1, 5, 5)
    battlefield.place_army(a1, 5, 8)
    battlefield.place_army(d2, 7, 5)
    battlefield.place_army(a2, 7, 6)

    # Destinations so armies move toward the primary defender
    a1.set_destination((5, 5))
    a2.set_destination((5, 5))

    # Use a smaller minimum spacing so armies can be within engagement range
    sim = MultiArmySimulator(battlefield, [a1, a2, d1, d2], min_spacing=1.0)

    # Establish initial duels: A1 vs D1 and A2 vs D2
    sim.set_targeting(a1, d1)
    sim.set_targeting(a2, d2)

    # Advance once; only A2 vs D2 should be engaged at this point
    sim.step()
    # Advance a second step so A1 engages D1 while A2 continues duelling D2
    sim.step()

    duel_a1_d1 = any(
        (d.army_a is a1 and d.army_b is d1) or (d.army_a is d1 and d.army_b is a1)
        for d in sim.active_duels
    )
    duel_a2_d2 = any(
        (d.army_a is a2 and d.army_b is d2) or (d.army_a is d2 and d.army_b is a2)
        for d in sim.active_duels
    )
    assert duel_a1_d1 and duel_a2_d2

    # Retarget A2 to attack D1 while still duelling D2
    sim.set_targeting(a2, d1)

    # Step once more; A2 should join the battle against D1
    sim.step()
    duel_a2_d1 = any(
        (d.army_a is a2 and d.army_b is d1) or (d.army_a is d1 and d.army_b is a2)
        for d in sim.active_duels
    )
    duel_a1_d1 = any(
        (d.army_a is a1 and d.army_b is d1) or (d.army_a is d1 and d.army_b is a1)
        for d in sim.active_duels
    )
    duel_a2_d2 = any(
        (d.army_a is a2 and d.army_b is d2) or (d.army_a is d2 and d.army_b is a2)
        for d in sim.active_duels
    )

    assert duel_a2_d1 and duel_a1_d1 and duel_a2_d2
    assert len(a2.active_duels) == 2
    assert len(d1.active_duels) == 2
