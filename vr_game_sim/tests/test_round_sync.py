from vr_game_sim.battlefield import Battlefield
from vr_game_sim.multi_army_simulator import MultiArmySimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.constants import EFFECT_NAME_FIRST_STRIKE_RAGE_AURA


def test_late_attacker_round_alignment():
    battlefield = Battlefield(20, 20)

    # Troop counts chosen so the first attacker survives until the second joins
    atk1 = Army("ATK1", Unit("infantry", 5, 200))
    atk2 = Army("ATK2", Unit("infantry", 5, 200))
    defender = Army("DEF", Unit("infantry", 5, 300))

    atk1.team = atk2.team = 1
    defender.team = 2

    battlefield.place_army(defender, 10, 10)
    # Attacker 1 starts close and engages first
    battlefield.place_army(atk1, 10, 13)
    # Attacker 2 is slightly further away so it joins a round later
    battlefield.place_army(atk2, 14, 10)

    atk1.set_destination((10, 10))
    atk2.set_destination((10, 10))

    sim = MultiArmySimulator(battlefield, [atk1, atk2, defender])
    sim.set_targeting(atk1, defender)
    sim.set_targeting(atk2, defender)

    # Run until the second attacker engages the defender
    for _ in range(20):
        sim.step()
        if len(defender.active_duels) == 2:
            break

    assert len(defender.active_duels) == 2

    duel_with_atk2 = next(d for d in defender.active_duels if atk2 in (d.army_a, d.army_b))
    duel_with_atk1 = next(d for d in defender.active_duels if atk1 in (d.army_a, d.army_b))

    # The new duel should inherit the defender's current round count
    current_round = defender.continuous_rounds
    assert duel_with_atk2.simulator.round == current_round

    # After another step both duels should advance to the same round
    sim.step()
    assert defender.continuous_rounds == current_round + 1
    assert duel_with_atk2.simulator.round == defender.continuous_rounds
    assert duel_with_atk1.simulator.round == defender.continuous_rounds


def test_late_attacker_independent_round_numbers():
    battlefield = Battlefield(20, 20)

    hero1 = Hero('H1', [], [], ['plugin_first_strike'], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero('H2', [], [], ['plugin_first_strike'], SKILL_REGISTRY_GLOBAL)
    atk1 = Army("ATK1", Unit("infantry", 5, 200), heroes=[hero1])
    atk2 = Army("ATK2", Unit("infantry", 5, 200), heroes=[hero2])
    defender = Army("DEF", Unit("infantry", 5, 300))

    atk1.team = atk2.team = 1
    defender.team = 2

    battlefield.place_army(defender, 10, 10)
    battlefield.place_army(atk1, 10, 13)
    battlefield.place_army(atk2, 14, 10)

    atk1.set_destination((10, 10))
    atk2.set_destination((10, 10))

    sim = MultiArmySimulator(battlefield, [atk1, atk2, defender])
    sim.set_targeting(atk1, defender)
    sim.set_targeting(atk2, defender)

    for _ in range(20):
        sim.step()
        if len(defender.active_duels) == 2:
            break

    assert len(defender.active_duels) == 2
    assert not any(e.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA for e in atk2.active_effects)

    sim.step()
    assert any(e.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA for e in atk1.active_effects)
    assert any(e.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA for e in atk2.active_effects)

