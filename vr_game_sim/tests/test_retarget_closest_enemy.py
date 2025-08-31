import random

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


def make_army(name: str, count: int = 100) -> Army:
    unit = Unit('pikemen', 5, initial_count=count)
    return Army(name, unit)


def test_no_auto_retarget_without_attackers():
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

    assert engine._armies['A'].direct_target is None


def test_retarget_prioritises_attackers_over_closest_enemy():
    random.seed(1)
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B')
    c = make_army('C')
    d = make_army('D')  # closer but not attacking
    e = make_army('E', 1)  # initial target that will die
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE + 10, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE + 20, 0), speed=0)
    engine.add_army(d, 'blue', position=(ENGAGEMENT_DISTANCE - 10, 0), speed=0)
    engine.add_army(e, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)

    engine.set_direct_target('B', 'A')
    engine.set_direct_target('C', 'A')
    engine.set_direct_target('A', 'E')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'B'


def test_retarget_randomly_selects_between_attackers_seed0():
    random.seed(0)
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B')
    c = make_army('C')
    d = make_army('D', 1)
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE + 10, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE + 20, 0), speed=0)
    engine.add_army(d, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)

    engine.set_direct_target('B', 'A')
    engine.set_direct_target('C', 'A')
    engine.set_direct_target('A', 'D')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'C'


def test_retarget_randomly_selects_between_attackers_seed1():
    random.seed(1)
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B')
    c = make_army('C')
    d = make_army('D', 1)
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE + 10, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE + 20, 0), speed=0)
    engine.add_army(d, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)

    engine.set_direct_target('B', 'A')
    engine.set_direct_target('C', 'A')
    engine.set_direct_target('A', 'D')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'B'
