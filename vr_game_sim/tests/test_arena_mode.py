import os
import random

import pytest

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
    a1 = make_army("A1", (0, 0), count=150)
    a2 = make_army("A2", (1, 0), count=150)
    b1 = make_army("B1", (0, 0), count=100)
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


def test_back_is_attacked_after_front_falls():
    front = make_army("Front", (0, 0), count=150)
    back = make_army("Back", (1, 1), count=50)
    enemy = make_army("Enemy", (0, 0), count=100)
    sim = ArenaSimulator([front, back], [enemy])
    sim.simulate_battle()
    assert back.current_troop_count < 50


def test_same_row_targeting_preferred():
    attacker = make_army("A", (0, 1), count=100)
    same_row_enemy = make_army("B", (1, 1), count=100)
    other_enemy = make_army("C", (0, 2), count=100)
    sim = ArenaSimulator([attacker], [same_row_enemy, other_enemy])
    target = sim._select_target(1, attacker.position, sim.armies_side2)
    assert target == same_row_enemy.position


def test_reactive_trigger_prefers_direct_target():
    defender = make_army("Def", (0, 0))
    atk1 = make_army("Atk1", (1, 0))
    atk2 = make_army("Atk2", (1, 1))
    chosen = ArenaSimulator.choose_reactive_trigger([atk1, atk2], defender_target=atk1)
    assert chosen is atk1


def test_reactive_trigger_random_choice_when_no_target():
    defender = make_army("Def", (0, 0))
    atk1 = make_army("Atk1", (1, 0))
    atk2 = make_army("Atk2", (1, 1))
    random.seed(0)
    chosen = ArenaSimulator.choose_reactive_trigger([atk1, atk2], defender_target=None)
    assert chosen is atk2


def test_battles_resolve_simultaneously():
    """Armies on different lanes should engage in the same round."""
    a1 = make_army("A1", (0, 0), count=100)
    a2 = make_army("A2", (0, 1), count=100)
    b1 = make_army("B1", (0, 0), count=100)
    b2 = make_army("B2", (0, 1), count=100)
    sim = ArenaSimulator([a1, a2], [b1, b2])
    sim.simulate_battle()
    # Both lane battles should resolve in a single round
    assert sim.round == 1


def test_rejects_more_than_eight_armies():
    armies = [make_army(f"A{i}", (0, 0)) for i in range(9)]
    with pytest.raises(ValueError):
        ArenaSimulator(armies, [])
    with pytest.raises(ValueError):
        ArenaSimulator([], armies)


def test_serialization_roundtrip_all_positions(tmp_path):
    positions = [(c, r) for r in range(4) for c in range(2)]
    side1 = []
    side2 = []
    for idx, pos in enumerate(positions):
        base = {
            "army_name": f"A{idx}",
            "unit_type": "infantry",
            "tier": 5,
            "count": 100,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "heroes": [],
            "grid_pos": list(pos),
        }
        side1.append(base)
        side2.append({**base, "army_name": f"B{idx}"})
    setup = {"side1": side1, "side2": side2}
    filename = "arena_all_slots.json"
    save_setup_to_file(setup, filename)
    loaded = load_setup_from_file(filename)
    os.remove(os.path.join(SETUPS_DIR, filename))
    armies1, armies2 = create_armies_from_data(loaded)
    assert {army.position for army in armies1} == set(positions)
    assert {army.position for army in armies2} == set(positions)


def test_all_lanes_resolve_in_single_round():
    side1 = [make_army(f"A{i}", (0, i), count=100) for i in range(4)]
    side2 = [make_army(f"B{i}", (0, i), count=100) for i in range(4)]
    sim = ArenaSimulator(side1, side2)
    sim.simulate_battle()
    assert sim.round == 1


def test_multiple_attackers_focus_single_enemy():
    """Several armies can sequentially attack the same target in one round."""
    a1 = make_army("A1", (0, 0), count=150)
    a2 = make_army("A2", (1, 0), count=150)
    b1 = make_army("B1", (0, 0), count=100)
    sim = ArenaSimulator([a1, a2], [b1])
    sim.simulate_battle()
    assert sim.winner == 1
    assert b1.current_troop_count <= 0


def test_left_slot5_target_priority():
    attacker = make_army("Atk", ArenaSimulator.LEFT_SLOT_TO_POS[5])
    enemy5 = make_army("E5", ArenaSimulator.RIGHT_SLOT_TO_POS[5])
    enemy6 = make_army("E6", ArenaSimulator.RIGHT_SLOT_TO_POS[6])
    sim = ArenaSimulator([attacker], [enemy5, enemy6])
    assert (
        sim._select_target(1, attacker.position, sim.armies_side2)
        == ArenaSimulator.RIGHT_SLOT_TO_POS[5]
    )
    del sim.armies_side2[ArenaSimulator.RIGHT_SLOT_TO_POS[5]]
    assert (
        sim._select_target(1, attacker.position, sim.armies_side2)
        == ArenaSimulator.RIGHT_SLOT_TO_POS[6]
    )


def test_right_slot3_target_priority():
    attacker = make_army("Atk", ArenaSimulator.RIGHT_SLOT_TO_POS[3])
    enemy3 = make_army("E3", ArenaSimulator.LEFT_SLOT_TO_POS[3])
    enemy4 = make_army("E4", ArenaSimulator.LEFT_SLOT_TO_POS[4])
    enemy1 = make_army("E1", ArenaSimulator.LEFT_SLOT_TO_POS[1])
    sim = ArenaSimulator([enemy3, enemy4, enemy1], [attacker])
    assert (
        sim._select_target(2, attacker.position, sim.armies_side1)
        == ArenaSimulator.LEFT_SLOT_TO_POS[3]
    )
    del sim.armies_side1[ArenaSimulator.LEFT_SLOT_TO_POS[3]]
    assert (
        sim._select_target(2, attacker.position, sim.armies_side1)
        == ArenaSimulator.LEFT_SLOT_TO_POS[4]
    )
    del sim.armies_side1[ArenaSimulator.LEFT_SLOT_TO_POS[4]]
    assert (
        sim._select_target(2, attacker.position, sim.armies_side1)
        == ArenaSimulator.LEFT_SLOT_TO_POS[1]
    )
