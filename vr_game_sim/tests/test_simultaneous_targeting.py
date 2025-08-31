import pytest

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def _run_single_engagement():
    engine = BattlefieldEngine()
    army_a = make_army("A")
    army_b = make_army("B")
    engine.add_army(army_a, "red", position=(0, 0), speed=0)
    engine.add_army(army_b, "blue", position=(2, 0), speed=0)
    engine.set_direct_target("A", "B")
    engine.tick(1.0)
    return army_a.current_troop_count, army_b.current_troop_count


def test_simultaneous_targets_share_single_engagement():
    expected_a, expected_b = _run_single_engagement()

    engine = BattlefieldEngine()
    army_a = make_army("A")
    army_b = make_army("B")
    engine.add_army(army_a, "red", position=(0, 0), speed=0)
    engine.add_army(army_b, "blue", position=(2, 0), speed=0)

    engine.set_direct_target("A", "B")
    engine.set_direct_target("B", "A")
    engine.tick(1.0)

    assert len(engine._engagements) == 1
    assert ("A", "B") in engine._engagements
    assert ("B", "A") not in engine._engagements
    assert army_a.current_troop_count == pytest.approx(expected_a)
    assert army_b.current_troop_count == pytest.approx(expected_b)

