import pytest
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def make_basic_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def test_idle_army_does_not_heal_in_arena():
    engine = ArenaEngine()
    attacker = make_basic_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)

    assert defender.current_troop_count < 1000
    pre_idle = defender.current_troop_count

    engine.set_direct_target("A", None)
    engine.set_direct_target("B", None)
    engine.tick(0.8)
    engine.tick(0.2)

    assert defender.current_troop_count == pytest.approx(pre_idle)
