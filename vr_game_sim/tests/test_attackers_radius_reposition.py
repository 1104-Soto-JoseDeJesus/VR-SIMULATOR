import math
import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=100000)
    return Army(name, unit)


def angle_between(engine: BattlefieldEngine, name: str, defender: str) -> float:
    atk = engine._armies[name]
    dfd = engine._armies[defender]
    ax, ay = atk.position
    dx, dy = dfd.position
    return (math.degrees(math.atan2(ay - dy, ax - dx)) + 360) % 360


def test_later_attacker_slides_clockwise_when_too_close():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(5)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-45, abs=1)


def test_switch_to_opposite_when_target_blocked_within_10_degrees():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    atk3 = make_army('A3')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-45)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    angle = math.radians(5)
    engine.add_army(
        atk3,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)
    engine.engage('A3', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang3 = angle_between(engine, 'A3', 'D')
    assert ang3 == pytest.approx(45, abs=1)


def test_flip_when_blocked_by_stationary_army_not_on_slot():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    atk3 = make_army('A3')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(30)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    angle = math.radians(5)
    engine.add_army(
        atk3,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)
    engine.engage('A3', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang3 = angle_between(engine, 'A3', 'D')
    assert ang3 == pytest.approx(315, abs=1)


def test_pushes_blocking_army_when_farther_than_10_degrees():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    atk3 = make_army('A3')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-45)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    angle = math.radians(-20)
    engine.add_army(
        atk3,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)
    engine.engage('A3', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang2 = angle_between(engine, 'A2', 'D')
    ang3 = angle_between(engine, 'A3', 'D')
    diff = (ang3 - ang2 + 180) % 360 - 180
    assert ang3 == pytest.approx(315, abs=1)
    assert diff == pytest.approx(45, abs=1)


def test_multiple_armies_same_direction_uses_25_degree_spacing():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    atk3 = make_army('A3')
    atk4 = make_army('A4')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-45)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    angle = math.radians(-90)
    engine.add_army(
        atk3,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    angle = math.radians(-20)
    engine.add_army(
        atk4,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)
    engine.engage('A3', 'D')
    engine.tick(1.0)
    engine.engage('A4', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang2 = angle_between(engine, 'A2', 'D')
    ang3 = angle_between(engine, 'A3', 'D')
    ang4 = angle_between(engine, 'A4', 'D')
    assert ang4 == pytest.approx(335, abs=1)
    assert ang2 == pytest.approx(310, abs=1)
    assert ang3 == pytest.approx(285, abs=1)


def test_clockwise_arrival_between_5_and_25_degrees_slides_clockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-24)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-45, abs=1)


def test_anticlockwise_arrival_between_5_and_25_degrees_slides_anticlockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(10)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(45, abs=1)


def test_between_26_and_44_degrees_clockwise_no_slide():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-30)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-30, abs=1)


def test_no_slide_when_more_than_44_degrees_clockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-50)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-50, abs=1)


def test_no_slide_when_more_than_25_degrees_anticlockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(30)
    engine.add_army(
        atk2,
        'red',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(30, abs=1)


def test_blue_team_attackers_reposition_like_red():
    engine = BattlefieldEngine()
    atk1 = make_army('B1')
    atk2 = make_army('B2')
    dfd = make_army('R')

    engine.add_army(atk1, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(5)
    engine.add_army(
        atk2,
        'blue',
        position=(math.cos(angle) * ENGAGEMENT_DISTANCE, math.sin(angle) * ENGAGEMENT_DISTANCE),
        speed=0,
    )
    engine.add_army(dfd, 'red', position=(0, 0), speed=0)

    engine.engage('B1', 'R')
    engine.tick(1.0)
    engine.engage('B2', 'R')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'B1', 'R')
    ang2 = angle_between(engine, 'B2', 'R')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-45, abs=1)


def test_same_angle_attacker_slides_clockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(atk2, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-45, abs=1)


def test_current_position_used_for_reposition():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(atk2, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    # Simulate a different approach path; the engine should ignore this
    engine._armies['A2'].path_start = (0, 2 * ENGAGEMENT_DISTANCE)
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    engine.engage('A1', 'D')
    engine.tick(1.0)
    engine.engage('A2', 'D')
    engine.tick(1.0)

    engine.tick(8.0)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(-45, abs=1)
