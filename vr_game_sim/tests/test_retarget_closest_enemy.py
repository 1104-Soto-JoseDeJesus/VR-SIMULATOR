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


def test_engage_does_not_swap_target_when_existing_alive():
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B')
    c = make_army('C')
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'blue', position=(ENGAGEMENT_DISTANCE, 0), speed=0)
    engine.add_army(c, 'blue', position=(ENGAGEMENT_DISTANCE, 10), speed=0)

    engine.engage('A', 'B')
    engine.engage('B', 'A')
    engine.tick(1.0)

    # Attempting to retarget while B is still alive should be ignored
    engine.engage('A', 'C')
    engine.tick(1.0)

    assert engine._armies['A'].direct_target == 'B'
    assert engine._armies['B'].direct_target == 'A'
    assert ('A', 'B') in engine._engagements
    assert ('A', 'C') not in engine._engagements
