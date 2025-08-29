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


def test_later_attacker_slides_clockwise_when_too_close():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(-5)
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
