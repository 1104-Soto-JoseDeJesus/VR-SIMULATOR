import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_cannot_target_same_team():
    engine = BattlefieldEngine()
    a = make_army('A')
    b = make_army('B')
    engine.add_army(a, 'red', speed=0)
    engine.add_army(b, 'red', speed=0)
    with pytest.raises(ValueError):
        engine.set_direct_target('A', 'B')
