import uuid
from vr_game_sim.duel import Duel
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType


def test_defender_effects_sync_between_duels():
    atk1 = Army("ATK1", Unit("infantry", 5, 10))
    atk2 = Army("ATK2", Unit("infantry", 5, 10))
    defender = Army("DEF", Unit("infantry", 5, 10))

    shield = EffectInstance(uuid.uuid4(), "test", EffectType.SHIELD, 1, 1)
    defender.active_effects.append(shield)

    duel1 = Duel(atk1, defender)
    duel2 = Duel(atk2, defender)

    duel1.sync_from_armies()
    res = duel1.simulate_round()
    assert res is not None
    for army, t_delta, u_delta in res["deltas"]:
        army.apply_round_results(t_delta, u_delta)

    assert len(defender.active_effects) == 0

    duel2.sync_from_armies()
    assert len(duel2.sim_b.active_effects) == 0
