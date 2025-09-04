from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE
from vr_game_sim.game_simulator import GameSimulator


def test_auto_targeted_defenders_reposition_around_attacker():
    unit = Unit('pikemen', 5, initial_count=10)
    red = Army('R', unit)
    blue1 = Army('B1', unit)
    blue2 = Army('B2', unit)
    engine = BattlefieldEngine()
    engine.add_army(red, 'red', position=(0, 0), speed=0)
    engine.add_army(blue1, 'blue', position=(ENGAGEMENT_DISTANCE, 10), speed=0)
    engine.add_army(blue2, 'blue', position=(ENGAGEMENT_DISTANCE, -10), speed=0)

    # Simulate red attacking both blue armies; use dummy simulators as values
    engine._engagements['R', 'B1'] = GameSimulator(red, blue1, None, track_stats=False)
    engine._engagements['R', 'B2'] = GameSimulator(red, blue2, None, track_stats=False)

    # Both defenders have auto-targeted the red attacker
    engine._armies['B1'].direct_target = 'R'
    engine._armies['B2'].direct_target = 'R'

    engine._step_movements(0.1)

    assert engine._armies['B1'].arc_index != engine._armies['B2'].arc_index
