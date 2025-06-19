import uuid
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_SHIELD_REFLECTOR_BUFF


def test_shield_reflector_triggers_next_round_only():
    hero = Hero('Tester', [], [], ['plugin_shield_reflector'], SKILL_REGISTRY_GLOBAL)
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL['plugin_shield_reflector']

    # Round 1 setup: army starts with a shield
    shield = EffectInstance(uuid.uuid4(), 'test_shield', EffectType.SHIELD, 1, 50)
    army.active_effects.append(shield)
    army.started_round_with_active_shield = True
    army.started_last_round_with_active_shield = False

    happened, _ = skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()

    assert not happened
    assert not any(e.name == EFFECT_NAME_SHIELD_REFLECTOR_BUFF for e in army.active_effects)

    # Round 2: previous round had shield, none now
    army.started_last_round_with_active_shield = army.started_round_with_active_shield
    army.started_round_with_active_shield = False

    happened, _ = skill_def['logic_handler'](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()

    assert happened
    assert any(e.name == EFFECT_NAME_SHIELD_REFLECTOR_BUFF for e in army.active_effects)
