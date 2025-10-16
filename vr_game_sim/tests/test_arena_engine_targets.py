import pytest
from math import hypot

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.battlefield_engine import ENGAGEMENT_DISTANCE
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def make_army_with_mods(
    name: str,
    *,
    atk_mod: float = 0.0,
    def_mod: float = 0.0,
    hp_mod: float = 0.0,
) -> Army:
    unit = Unit(
        "pikemen",
        5,
        initial_count=1000,
        initial_atk_modifier=atk_mod,
        initial_def_modifier=def_mod,
        initial_hp_modifier=hp_mod,
    )
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


def test_str_targeting_prioritises_strongest_and_advances():
    engine = ArenaEngine()
    attacker = make_army("attacker")
    strong = make_army_with_mods("strong", atk_mod=0.5)
    medium = make_army_with_mods("medium", atk_mod=0.2)
    weak = make_army_with_mods("weak", atk_mod=-0.1)

    layout = {
        "red": [
            {"army": attacker, "position": (0.0, 0.0), "column": 0, "row": 0},
        ],
        "blue": [
            {"army": strong, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": medium, "position": (100.0, 200.0), "column": 1, "row": 0},
            {"army": weak, "position": (-100.0, 200.0), "column": 2, "row": 0},
        ],
    }

    engine.start_arena_battle(layout, targeting_mode="str")

    assert engine._armies[attacker.name].direct_target == strong.name
    engine._remove_army(strong.name)
    assert engine._armies[attacker.name].direct_target == medium.name
    engine._remove_army(medium.name)
    assert engine._armies[attacker.name].direct_target == weak.name


@pytest.mark.parametrize("mode", ["str", "frg"])
def test_str_frg_modes_preserve_base_speeds(mode: str) -> None:
    engine = ArenaEngine()
    attacker = make_army("attacker")
    defender_primary = make_army("primary")
    defender_secondary = make_army("secondary")

    layout = {
        "red": [
            {
                "army": attacker,
                "position": (0.0, 0.0),
                "column": 0,
                "row": 0,
                "speed": 37.0,
            }
        ],
        "blue": [
            {
                "army": defender_primary,
                "position": (0.0, 200.0),
                "column": 0,
                "row": 0,
                "speed": 41.5,
            },
            {
                "army": defender_secondary,
                "position": (100.0, 200.0),
                "column": 1,
                "row": 0,
                "speed": 33.3,
            },
        ],
    }

    expected_speeds = {
        attacker.name: 37.0,
        defender_primary.name: 41.5,
        defender_secondary.name: 33.3,
    }

    engine.start_arena_battle(layout, targeting_mode=mode)

    for name, speed in expected_speeds.items():
        ctx = engine._armies[name]
        assert ctx.base_speed == pytest.approx(speed)
        assert ctx.speed == pytest.approx(speed)

    assert engine.default_speed == pytest.approx(expected_speeds[attacker.name])


def test_frg_targeting_prioritises_fragile_and_advances():
    engine = ArenaEngine()
    attacker = make_army("attacker")
    fragile = make_army_with_mods("fragile", def_mod=-0.3, hp_mod=-0.3)
    middle = make_army_with_mods("middle", def_mod=0.0, hp_mod=0.1)
    sturdy = make_army_with_mods("sturdy", def_mod=0.5, hp_mod=0.5)

    layout = {
        "red": [
            {"army": attacker, "position": (0.0, 0.0), "column": 0, "row": 0},
        ],
        "blue": [
            {"army": fragile, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": middle, "position": (100.0, 200.0), "column": 1, "row": 0},
            {"army": sturdy, "position": (-100.0, 200.0), "column": 2, "row": 0},
        ],
    }

    engine.start_arena_battle(layout, targeting_mode="frg")

    assert engine._armies[attacker.name].direct_target == fragile.name
    engine._remove_army(fragile.name)
    assert engine._armies[attacker.name].direct_target == middle.name
    engine._remove_army(middle.name)
    assert engine._armies[attacker.name].direct_target == sturdy.name


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


def test_diagonal_misaligned_target_speed_boost():
    engine = ArenaEngine()
    diag = make_army("diag")
    front = make_army("front")
    enemy = make_army("enemy")

    layout = {
        "red": [
            {"army": front, "position": (-130.0, 37.5), "column": 2, "row": 0},
            {"army": diag, "position": (-130.0, 112.5), "column": 3, "row": 0},
        ],
        "blue": [
            {"army": enemy, "position": (130.0, -37.5), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    ctx_diag = engine._armies[diag.name]
    ctx_enemy = engine._armies[enemy.name]

    sx, sy = ctx_diag.position
    tx, ty = ctx_enemy.position
    dist = hypot(tx - sx, ty - sy)
    required_sum = (dist - ENGAGEMENT_DISTANCE) / 1.87
    def_ctx = engine._armies[ctx_enemy.direct_target]
    mx, my = def_ctx.position[0] - tx, def_ctx.position[1] - ty
    mv_dist = hypot(mx, my)
    ux, uy = mx / mv_dist, my / mv_dist
    ax = (tx - sx) / dist
    ay = (ty - sy) / dist
    expected_speed = required_sum + ctx_enemy.speed * (ax * ux + ay * uy)

    assert ctx_diag.speed == pytest.approx(expected_speed, abs=0.01)
