from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def test_front_rows_target_and_meet_midpoint():
    engine = ArenaEngine()
    a_front = make_army("A_front")
    a_back = make_army("A_back")
    b_front = make_army("B_front")
    b_back = make_army("B_back")

    layout = {
        "red": [
            {"army": a_front, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_back, "position": (0.0, -200.0), "column": 0, "row": 1},
        ],
        "blue": [
            {"army": b_front, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": b_back, "position": (0.0, 400.0), "column": 0, "row": 1},
        ],
    }

    engine.start_arena_battle(layout)

    assert engine._armies[a_front.name].direct_target == b_front.name
    assert engine._armies[a_back.name].direct_target == b_front.name
    assert engine._armies[b_front.name].direct_target == a_front.name
    assert engine._armies[b_back.name].direct_target == a_front.name

    midpoint = (0.0, 100.0)
    assert engine._armies[a_front.name].path == [midpoint]
    assert engine._armies[b_front.name].path == [midpoint]


def test_fallback_to_back_slot_when_front_missing():
    engine = ArenaEngine()
    a_front = make_army("A_front")
    a_back = make_army("A_back")
    b_back = make_army("B_back")

    layout = {
        "red": [
            {"army": a_front, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_back, "position": (0.0, -200.0), "column": 0, "row": 1},
        ],
        "blue": [
            {"army": b_back, "position": (0.0, 400.0), "column": 0, "row": 1},
        ],
    }

    engine.start_arena_battle(layout)

    assert engine._armies[a_front.name].direct_target == b_back.name
    assert engine._armies[a_back.name].direct_target == b_back.name
    assert engine._armies[b_back.name].direct_target == a_front.name
