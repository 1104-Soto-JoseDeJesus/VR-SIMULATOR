from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine


def test_engine_reset_clears_state_and_clock() -> None:
    unit = Unit('pikemen', 5, initial_count=1000)
    army_a = Army('A', unit)
    unit_b = Unit('archers', 5, initial_count=1000)
    army_b = Army('B', unit_b)
    engine = BattlefieldEngine()
    engine.add_army(army_a, 'red', position=(1.0, 0.0))
    engine.add_army(army_b, 'blue', position=(2.0, 0.0))
    engine.engage('A', 'B')
    engine.tick(1.0)

    assert engine.time_elapsed == 1.0
    assert engine._armies
    assert engine._engagements

    engine.reset()

    assert engine.time_elapsed == 0.0
    assert engine._round_accumulator == 0.0
    assert engine._sub_accumulator == 0.0
    assert engine._armies == {}
    assert engine._engagements == {}
    assert engine._graph == {}
