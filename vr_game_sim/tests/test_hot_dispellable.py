import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.constants import EFFECT_NAME_PENDING_HEIMDALL_DISPEL
from vr_game_sim.enums import EffectType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.plugin_skill_handlers import handle_plugin_hymn_of_life
from vr_game_sim.skill_logic.talent_handlers import handle_talent_maniacal
from vr_game_sim.unit_definition import Unit


def _activate_next_round_effects(army: Army) -> None:
    if army.effects_to_activate_next_round:
        army.upcoming_effects.extend(army.effects_to_activate_next_round)
        army.effects_to_activate_next_round.clear()


@pytest.mark.parametrize(
    "skill_id, handler",
    [
        ("talent_maniacal", handle_talent_maniacal),
        ("plugin_hymn_of_life", handle_plugin_hymn_of_life),
    ],
)
def test_hot_effects_can_be_dispelled(skill_id, handler):
    army = Army(name="Army", unit=Unit(unit_type="infantry", tier=5, initial_count=100))
    enemy = Army(name="Enemy", unit=Unit(unit_type="infantry", tier=5, initial_count=100))
    simulator = GameSimulator(army, enemy)

    skill_def = SKILL_REGISTRY_GLOBAL[skill_id]
    happened, _ = handler(army, enemy, skill_def, None, simulator)
    assert happened

    _activate_next_round_effects(army)
    army.activate_queued_effects()

    dispellable_hots = [
        eff
        for eff in army.active_effects
        if eff.effect_type == EffectType.HEAL_OVER_TIME and eff.is_dispellable_buff_candidate()
    ]
    assert dispellable_hots, "Heal over time effects should be dispellable"
    hot_effect = dispellable_hots[0]

    dispel_effect = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
        "duration": 0,
        "config": {"buff_ids_to_remove": [hot_effect.id]},
        "activate_next_round": True,
    }
    army._create_and_add_single_effect(dispel_effect, "dispel_skill", enemy, army, enemy)

    _activate_next_round_effects(army)
    army.activate_queued_effects()
    army.process_periodic_effects("start_of_round", opponent=enemy)

    assert all(eff.id != hot_effect.id for eff in army.active_effects)
