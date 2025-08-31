import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_engagement_gated_and_rage_round_updates():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)

    engine.tick(0.3)
    engine.engage('A', 'B')  # schedule for t=1
    engine.tick(0.5)
    assert ('A', 'B') not in engine._engagements
    engine.tick(0.2)  # reach t=1
    assert ('A', 'B') in engine._engagements
    ctx_a = engine._armies['A']
    assert ctx_a.internal_round == 1
    assert army_a.current_rage == 100


def test_internal_rounds_are_per_attacker():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    army_c = make_army('C')
    for army, team in [(army_a, 'red'), (army_b, 'blue'), (army_c, 'red')]:
        engine.add_army(army, team, speed=0)

    engine.tick(0.3)
    engine.engage('A', 'B')
    engine.tick(0.7)  # t=1, first round
    engine.tick(1.0)  # t=2, second round
    engine.tick(0.2)
    engine.engage('C', 'B')
    engine.tick(0.8)  # t=3, third round for A, first for C

    ctx_a = engine._armies['A']
    ctx_c = engine._armies['C']
    assert ctx_a.internal_round == 3
    assert ctx_c.internal_round == 1


def test_round_and_rage_stop_after_idle():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)

    engine.tick(0.3)
    engine.engage('A', 'B')
    engine.tick(0.7)  # t=1
    engine.tick(1.0)  # t=2
    engine.tick(1.0)  # t=3
    ctx_a = engine._armies['A']
    assert ctx_a.internal_round == 3
    assert army_a.current_rage == 300

    # Kill the defender to end the engagement; idle time resets counters
    engine._armies['B'].army.current_troop_count = 0
    engine.tick(1.0)
    ctx_a = engine._armies['A']
    assert ctx_a.internal_round == 0
    assert army_a.current_rage == 0
    assert ctx_a.last_engaged_time == pytest.approx(3.0)


def test_both_armies_attack_each_round():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', position=(0, 0), speed=0)
    engine.add_army(army_b, 'blue', position=(2, 0), speed=0)

    engine.engage('A', 'B')
    engine.tick(1.0)

    assert army_a.current_troop_count < 1000
    assert army_b.current_troop_count < 1000
