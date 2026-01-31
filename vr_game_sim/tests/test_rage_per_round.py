from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_DELAYED_RAGE_REDUCTION
import uuid


def test_rage_per_round_tracks_only_additions():
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, fairness_rage_enabled=False)
    sim.round = 1
    army.army_round = enemy.army_round = 1

    army.current_rage = 200
    eff = EffectInstance(
        uuid.uuid4(),
        'test',
        EffectType.CUSTOM_SKILL_EFFECT,
        duration=0,
        config={'rage_reduction': 150},
        name=EFFECT_NAME_DELAYED_RAGE_REDUCTION,
    )
    army.active_effects.append(eff)

    army.apply_start_of_round_rage_deductions()
    sim._apply_base_rage_gain()

    army.rage_gained_history.append(army.rage_added_this_round)

    assert army.current_rage == 150
    assert army.rage_gained_history[-1] == 100
