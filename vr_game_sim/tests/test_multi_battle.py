import random

from vr_game_sim.main import run_multi_battle, create_armies_from_data
from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.constants import ENGAGEMENT_RADIUS


def test_multi_battle_runs():
    setup = [
        {
            "army_name": "A1",
            "unit_type": "infantry",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "A2",
            "unit_type": "archers",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "A3",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
    ]
    armies = run_multi_battle(setup, max_rounds=50, seed=1)
    assert len(armies) >= 1
    assert any(a.current_troop_count < a.unit.initial_count for a in armies)


def test_multiple_attackers_can_engage_same_defender():
    random.seed(0)
    setup = [
        {
            "army_name": "ATK1",
            "unit_type": "infantry",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "ATK2",
            "unit_type": "infantry",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "DEF",
            "unit_type": "infantry",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
    ]

    atk1, atk2, defender = create_armies_from_data(setup)
    atk1.team = atk2.team = 1
    defender.team = 2
    battlefield = Battlefield(10, 10)
    battlefield.place_army(defender, 5, 5)
    battlefield.place_army(atk1, 5, 8)
    battlefield.place_army(atk2, 8, 5)
    atk1.set_destination((5, 5))
    atk2.set_destination((5, 5))

    sim = MultiArmySimulator(battlefield, [atk1, atk2, defender])

    # Run until both attackers have engaged the defender
    for _ in range(10):
        sim.step()
        if len(defender.active_duels) == 2:
            break

    assert len(defender.active_duels) == 2
    assert defender.direct_target in (atk1, atk2)
    assert len(defender.attackers) == 2
    assert atk1 in defender.attackers and atk2 in defender.attackers

    pre_counts = (
        atk1.current_troop_count,
        atk2.current_troop_count,
        defender.current_troop_count,
    )

    for _ in range(5):
        sim.step()

    assert atk1.current_troop_count < pre_counts[0]
    assert atk2.current_troop_count < pre_counts[1]
    assert defender.current_troop_count < pre_counts[2]


def test_armies_engage_within_radius():
    battlefield = Battlefield(10, 10)
    atk = Army("ATK", Unit("infantry", 5, 50))
    atk.team = 1
    defn = Army("DEF", Unit("archers", 5, 50))
    defn.team = 2
    battlefield.place_army(atk, 0, 0)
    battlefield.place_army(defn, ENGAGEMENT_RADIUS, 0)
    sim = MultiArmySimulator(battlefield, [atk, defn])
    sim.step()
    assert len(sim.active_duels) == 1
