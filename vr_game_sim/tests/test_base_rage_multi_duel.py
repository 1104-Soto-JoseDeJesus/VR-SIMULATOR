import random

from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_defender_only_receives_base_rage_once_with_multiple_attackers():
    random.seed(0)
    battlefield = Battlefield(10, 10)
    defender = Army("Def", Unit("infantry", 5, 100), team=1)
    attacker1 = Army("Atk1", Unit("infantry", 5, 100), team=2)
    attacker2 = Army("Atk2", Unit("infantry", 5, 100), team=2)
    sim = MultiArmySimulator(battlefield, [defender, attacker1, attacker2])
    battlefield.place_army(defender, 5, 5)
    battlefield.place_army(attacker1, 5, 4)
    battlefield.place_army(attacker2, 5, 6)
    sim._resolve_battle(attacker1, defender)
    sim._resolve_battle(attacker2, defender)
    sim.step()  # advance one round for both duels
    assert defender.current_rage == 100
