import random
from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_defender_counters_all_attackers_before_death():
    random.seed(0)
    battlefield = Battlefield(10, 10)
    defender = Army("Def", Unit("infantry", 5, 50), team=1)
    atk1 = Army("Atk1", Unit("infantry", 5, 500), team=2)
    atk2 = Army("Atk2", Unit("infantry", 5, 500), team=2)
    battlefield.place_army(defender, 5, 5)
    battlefield.place_army(atk1, 5, 4)
    battlefield.place_army(atk2, 5, 6)
    sim = MultiArmySimulator(battlefield, [defender, atk1, atk2])
    sim._resolve_battle(atk1, defender)
    sim._resolve_battle(atk2, defender)
    sim.step()
    assert defender.current_troop_count == 0
    assert atk1.current_troop_count < 500
    assert atk2.current_troop_count < 500
