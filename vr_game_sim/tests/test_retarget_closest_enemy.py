import random

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def make_army(name: str, count: int = 100) -> Army:
    unit = Unit('pikemen', 5, initial_count=count)
    return Army(name, unit)


def test_retarget_picks_closest_enemy():
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B', 1)
    c = make_army('C')
    d = make_army('D')
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE + 5, 0), speed=0)
    engine.add_army(d, 'blue', position=(ENGAGEMENT_DISTANCE + 20, 0), speed=0)

    engine.set_direct_target('A', 'B')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'C'


def test_retarget_uses_random_when_distances_equal():
    random.seed(1)
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B', 1)
    c = make_army('C')
    d = make_army('D')
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE + 10, 0), speed=0)
    engine.add_army(d, 'blue', position=(-ENGAGEMENT_DISTANCE - 10, 0), speed=0)

    engine.set_direct_target('A', 'B')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'C'
