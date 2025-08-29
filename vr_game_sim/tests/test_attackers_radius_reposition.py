import math
import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def angle_between(engine: BattlefieldEngine, name: str, defender: str) -> float:
    atk = engine._armies[name]
    dfd = engine._armies[defender]
    ax, ay = atk.position
    dx, dy = dfd.position
    return (math.degrees(math.atan2(ay - dy, ax - dx)) + 360) % 360


def test_later_attacker_slides_anticlockwise_when_too_close():
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
    assert diff == pytest.approx(45, abs=1)


def test_clockwise_arrival_within_15_degrees_still_slides_anticlockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-14)
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


def test_later_attacker_slides_clockwise_when_more_than_15_degrees_clockwise():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-16)
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


def test_same_angle_attacker_slides_anticlockwise():
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
    assert diff == pytest.approx(45, abs=1)


def test_waypoint_start_angle_used_for_reposition():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)
    engine.engage('A1', 'D')
    engine.tick(1.0)

    engine.add_army(atk2, 'red', position=(0, 2 * ENGAGEMENT_DISTANCE), speed=140)
    engine.set_direct_target('A2', 'D', pursue=False)
    engine.set_waypoint('A2', (ENGAGEMENT_DISTANCE, 0))

    engine.tick(2.0)
    engine.tick(0.1)

    ang1 = angle_between(engine, 'A1', 'D')
    ang2 = angle_between(engine, 'A2', 'D')
    diff = (ang2 - ang1 + 180) % 360 - 180
    assert diff == pytest.approx(0, abs=1)
