from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.battlefield_engine import ENGAGEMENT_DISTANCE


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def test_back_row_units_engage_front_defenders_round3():
    engine = ArenaEngine()

    r_left = make_army("R_left")
    r_right = make_army("R_right")
    b_left = make_army("B_left")
    b_right = make_army("B_right")

    r_back_y = -ENGAGEMENT_DISTANCE * 2
    b_front_y = ENGAGEMENT_DISTANCE * 2

    layout = {
        "red": [
            {"army": r_left, "position": (0.0, r_back_y), "column": 0, "row": 1},
            {"army": r_right, "position": (300.0, r_back_y), "column": 1, "row": 1},
        ],
        "blue": [
            {"army": b_left, "position": (300.0, b_front_y), "column": 0, "row": 0},
            {"army": b_right, "position": (0.0, b_front_y), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(3):
        engine.tick(1.0)

    engagements = {frozenset(k) for k in engine._engagements.keys()}
    assert frozenset((r_left.name, b_left.name)) in engagements
    assert frozenset((r_right.name, b_right.name)) in engagements

