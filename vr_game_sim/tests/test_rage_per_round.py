from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_DELAYED_RAGE_REDUCTION
import uuid
from vr_game_sim.skill_logic.gem_skill_handlers import handle_gem_skill_lower_troop_periodic_composite
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


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
    # Base rage is now granted on basic attack; simulate army basic attacking
    sim._calculate_and_log_attack(army, enemy, is_counter=False)

    army.rage_gained_history.append(army.rage_added_this_round)

    assert army.current_rage == 150
    assert army.rage_gained_history[-1] == 100


def test_conquering_waves_aura_grants_periodic_rage_and_tracks_source():
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, fairness_rage_enabled=False)

    aura = EffectInstance(
        uuid.uuid4(),
        'gem_heimdalls_sapphire_conquering_waves_legendary',
        EffectType.CUSTOM_SKILL_EFFECT,
        duration=30,
        config={
            'rage_per_round': 75,
            'start_rage_gain_round': 2,
            'end_rage_gain_round': 31,
        },
        name="Heimdall's Sapphire • Conquering Waves Aura (Legendary)",
    )
    aura.applied_this_round = False
    army.active_effects.append(aura)

    sim.round = 1
    army.army_round = enemy.army_round = 1
    army.process_periodic_effects('start_of_round', enemy)
    assert army.current_rage == 0

    sim.round = 2
    army.army_round = enemy.army_round = 2
    army.process_periodic_effects('start_of_round', enemy)

    sim.round = 3
    army.army_round = enemy.army_round = 3
    army.process_periodic_effects('start_of_round', enemy)

    assert army.current_rage == 150
    assert army.skill_rage_totals.get('gem_heimdalls_sapphire_conquering_waves_legendary') == 150


def test_seas_voyage_delayed_rage_applies_next_round():
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, fairness_rage_enabled=False)
    skill = SKILL_REGISTRY_GLOBAL['gem_odins_amber_seas_voyage_legendary']

    sim.round = 9
    army.army_round = enemy.army_round = 9
    triggered, _ = handle_gem_skill_lower_troop_periodic_composite(army, enemy, skill, {}, sim)
    assert triggered is True
    assert len(army.effects_to_activate_next_round) == 1

    sim.round = 10
    army.army_round = enemy.army_round = 10
    army.upcoming_effects.extend(army.effects_to_activate_next_round)
    army.effects_to_activate_next_round.clear()
    army.activate_queued_effects()
    army.decrement_effect_durations()
    army.process_periodic_effects('start_of_round', enemy)

    assert army.current_rage == 200
    assert army.skill_rage_totals.get('gem_odins_amber_seas_voyage_legendary') == 200
