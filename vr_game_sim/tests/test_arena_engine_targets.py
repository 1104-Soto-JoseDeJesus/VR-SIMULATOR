from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.battlefield_engine import ENGAGEMENT_DISTANCE
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def test_front_rows_target_and_meet_midpoint():
    engine = ArenaEngine()
    a_front = make_army("A_front")
    a_back = make_army("A_back")
    b_front = Army("B_front", Unit("pikemen", 5, initial_count=1500))
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


def test_retarget_back_before_closest():
    engine = ArenaEngine()
    a_front = make_army("A_front")
    a_back = make_army("A_back")
    b_front = Army("B_front", Unit("pikemen", 5, initial_count=1))
    b_back = make_army("B_back")
    b_other = make_army("B_other")

    layout = {
        "red": [
            {"army": a_front, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_back, "position": (0.0, -200.0), "column": 0, "row": 1},
        ],
        "blue": [
            {"army": b_front, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": b_back, "position": (0.0, 400.0), "column": 0, "row": 1},
            {"army": b_other, "position": (300.0, 200.0), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(20):
        engine.tick(1.0)
        if "B_front" not in engine._armies:
            break

    assert "B_front" not in engine._armies
    assert engine._armies[a_front.name].direct_target == b_back.name
    assert engine._armies[a_back.name].direct_target == b_back.name


def test_arena_retains_initial_direct_target():
    engine = ArenaEngine()
    a = make_army("A")
    b = make_army("B")
    c = make_army("C")

    engine.add_army(a, "red", position=(0.0, 0.0), speed=0)
    engine.add_army(b, "blue", position=(0.0, 200.0), speed=0)
    engine.add_army(c, "blue", position=(0.0, 400.0), speed=0)

    engine.engage("A", "B")
    engine.engage("A", "C")

    assert engine._armies[a.name].direct_target == b.name


def test_front_unit_attacks_back_only_after_front_defeated():
    report_builder = BattlefieldReportBuilder()
    engine = ArenaEngine(report_builder)

    a_front = make_army("A_front")
    a_back = make_army("A_back")
    b_front = Army("B_front", Unit("pikemen", 5, initial_count=1500))

    layout = {
        "red": [
            {"army": a_front, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_back, "position": (0.0, -ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 1},
        ],
        "blue": [
            {"army": b_front, "position": (0.0, ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    pre_defeat_rounds: list = []
    for _ in range(200):
        engine.tick(1.0)
        rounds = report_builder.get_rounds()
        ab_rounds = rounds.get((a_back.name, b_front.name))
        if ab_rounds and not pre_defeat_rounds:
            pre_defeat_rounds = list(ab_rounds)
            assert engine._armies[b_front.name].direct_target == a_front.name
        if a_front.name not in engine._armies:
            break

    assert pre_defeat_rounds and a_front.name not in engine._armies and b_front.name in engine._armies

    assert not any(
        action["attacker_name"] == b_front.name and action["action_type"] == "Basic Attack"
        for round_data in pre_defeat_rounds
        for action in round_data["combat_actions"]
    )

    for _ in range(5):
        engine.tick(1.0)

    rounds_after = report_builder.get_rounds().get((a_back.name, b_front.name), [])
    post_rounds = rounds_after[len(pre_defeat_rounds) :]

    assert any(
        action["attacker_name"] == b_front.name and action["action_type"] == "Basic Attack"
        for round_data in post_rounds
        for action in round_data["combat_actions"]
    )
