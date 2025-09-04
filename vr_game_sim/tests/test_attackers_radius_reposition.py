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

@pytest.mark.parametrize("offset", [5, -5])
def test_second_attacker_moves_clockwise_when_close(offset):
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(offset)
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
    assert angle_between(engine, 'A2', 'D') == pytest.approx(315, abs=1)

def test_third_attacker_prefers_less_populated_side():
    engine = BattlefieldEngine()
    atk1 = make_army('A1')
    atk2 = make_army('A2')
    atk3 = make_army('A3')
    dfd = make_army('D')

    engine.add_army(atk1, 'red', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    angle = math.radians(45)
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
    assert angle_between(engine, 'A3', 'D') == pytest.approx(315, abs=1)

def test_ref_degrees_shrinks_existing_positions():
    engine = BattlefieldEngine()
    names = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
    angles = [0, 45, -45, 90, -90, 5]
    for nm, ang in zip(names, angles):
        r = math.radians(ang)
        engine.add_army(
            make_army(nm),
            'red',
            position=(math.cos(r) * ENGAGEMENT_DISTANCE, math.sin(r) * ENGAGEMENT_DISTANCE),
            speed=0,
        )
    dfd = make_army('D')
    engine.add_army(dfd, 'blue', position=(0, 0), speed=0)

    for nm in names[:-1]:
        engine.engage(nm, 'D')
        engine.tick(1.0)
    engine.tick(8.0)

    engine.engage('A6', 'D')
    engine.tick(1.0)
    engine.tick(8.0)

    assert angle_between(engine, 'A2', 'D') == pytest.approx(30, abs=1)
    assert angle_between(engine, 'A3', 'D') == pytest.approx(330, abs=1)
    assert angle_between(engine, 'A4', 'D') == pytest.approx(60, abs=1)
    assert angle_between(engine, 'A5', 'D') == pytest.approx(300, abs=1)
    assert angle_between(engine, 'A6', 'D') == pytest.approx(90, abs=1)
