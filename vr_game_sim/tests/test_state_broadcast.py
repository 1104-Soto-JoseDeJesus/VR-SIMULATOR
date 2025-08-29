import uuid
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, StatType


def make_army(name: str) -> Army:
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit)


def test_state_broadcast_on_effect_and_shield_change():
    engine = BattlefieldEngine()
    army_a = make_army('A')
    army_b = make_army('B')
    engine.add_army(army_a, 'red', speed=0)
    engine.add_army(army_b, 'blue', speed=0)

    events = []
    engine.add_state_listener(lambda name, state: events.append((name, state)))

    # Defender starts with a tiny shield that will be removed and a buff that
    # becomes active at the start of combat.
    shield = EffectInstance(uuid.uuid4(), 'skill', EffectType.SHIELD, duration=1, magnitude=1)
    buff = EffectInstance(
        uuid.uuid4(), 'skill', EffectType.STAT_MOD, duration=1, magnitude=0.1,
        config={'stat_to_mod': StatType.BASIC_DAMAGE_ADJUST}
    )
    army_b.active_effects.append(shield)
    army_b.upcoming_effects.append(buff)

    engine.tick(0.3)
    engine.engage('A', 'B')
    engine.tick(0.7)  # triggers first round and broadcasts state

    b_updates = [state for name, state in events if name == 'B']
    assert b_updates, 'Defender state update not broadcast'
    last_state = b_updates[-1]

    # Rage should have increased and shield consumed
    assert last_state['rage'] == 100
    assert last_state['shield_hp'] == 0
    assert buff in last_state['active_effects']
    assert all(e.effect_type != EffectType.SHIELD for e in last_state['active_effects'])
