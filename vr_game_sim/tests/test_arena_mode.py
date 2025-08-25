import os

from vr_game_sim.arena_simulator import ArenaSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.main import (
    save_setup_to_file,
    load_setup_from_file,
    create_armies_from_data,
    SETUPS_DIR,
)


def make_army(name, pos, count=100):
    unit = Unit("infantry", 5, initial_count=count)
    army = Army(name, unit, [])
    army.position = pos
    return army


def test_arena_winner():
    a1 = make_army("A1", (0, 0))
    a2 = make_army("A2", (1, 0))
    b1 = make_army("B1", (0, 0))
    sim = ArenaSimulator([a1, a2], [b1])
    sim.simulate_battle()
    assert sim.winner == 1


def test_empty_slot_targets_nearest():
    a1 = make_army("A1", (0, 0))
    b1 = make_army("B1", (1, 0))
    sim = ArenaSimulator([a1], [b1])
    sim.simulate_battle()
    assert sim.round > 0


def test_serialization_roundtrip(tmp_path):
    setup = {
        "side1": [
            {
                "army_name": "A1",
                "unit_type": "infantry",
                "tier": 5,
                "count": 100,
                "atk_mod": 0.0,
                "def_mod": 0.0,
                "hp_mod": 0.0,
                "heroes": [],
                "grid_pos": [0, 0],
            }
        ],
        "side2": [
            {
                "army_name": "B1",
                "unit_type": "infantry",
                "tier": 5,
                "count": 100,
                "atk_mod": 0.0,
                "def_mod": 0.0,
                "hp_mod": 0.0,
                "heroes": [],
                "grid_pos": [1, 0],
            }
        ],
    }
    filename = "arena_test.json"
    save_setup_to_file(setup, filename)
    loaded = load_setup_from_file(filename)
    os.remove(os.path.join(SETUPS_DIR, filename))
    armies1, armies2 = create_armies_from_data(loaded)
    assert armies1[0].position == (0, 0)
    assert armies2[0].position == (1, 0)
