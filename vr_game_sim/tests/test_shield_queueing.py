from vr_game_sim.army_composition import Army
from vr_game_sim.enums import EffectType
from vr_game_sim.unit_definition import Unit


def test_shield_effects_always_delayed_to_next_round():
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[])
    opponent = Army("B", Unit("archers", 5, initial_count=10), heroes=[])

    shield_data = {
        "effect_type": EffectType.SHIELD,
        "name": "Queued Shield",
        "duration": 1,
        "magnitude": 100,
        "activate_next_round": False,
    }

    inst = army._create_and_add_single_effect(
        shield_data,
        "test_skill",
        army,
        army,
        opponent,
    )

    assert inst is not None
    assert not army.upcoming_effects
    assert len(army.effects_to_activate_next_round) == 1

    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()

    army.activate_queued_effects()

    assert inst in army.active_effects
    assert not army.effects_to_activate_next_round

