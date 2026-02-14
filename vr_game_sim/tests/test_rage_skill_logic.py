import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.constants import EFFECT_NAME_FIRST_STRIKE_RAGE_AURA, EFFECT_NAME_SILENCE_DEBUFF
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def make_army_with_rage_skill(name="Army"):
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    return Army(name, unit, heroes=[hero])


def test_rage_skill_cancels_when_insufficient_rage():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2, mode="arena")
    sim.round = 1

    army1.current_rage = 900
    army1.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(army1, army2)

    assert not army1.hero1_rage_skill_queued_this_round
    assert army1.current_rage == 900


def test_no_base_rage_when_skill_cast():
    """On trigger round, no rage is gained from any source including base rage on basic attack."""
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mode="arena")
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    army1.current_rage = 1000
    army1.hero1_rage_skill_queued_this_round = True
    sim._execute_rage_skills(army1, army2)
    # Simulate army1 basic attack - base rage would be blocked on trigger round
    sim._calculate_and_log_attack(army1, army2, is_counter=False)

    assert army1.current_rage == 0
    assert not army1.base_rage_awarded_this_round


def test_base_rage_awarded_when_skill_canceled():
    """When skill is canceled (insufficient rage), army gets base rage from basic attack."""
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mode="arena", fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    army1.current_rage = 900
    army1.hero1_rage_skill_queued_this_round = True
    sim._execute_rage_skills(army1, army2)  # Cancels due to insufficient rage
    # Army basic attacks - gets base rage (not trigger round since skill didn't fire)
    sim._calculate_and_log_attack(army1, army2, is_counter=False)

    assert army1.current_rage == 1000
    assert army1.base_rage_awarded_this_round


def test_base_rage_blocked_when_disarmed():
    """When disarmed, army cannot basic attack and gets no base rage."""
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mode="arena", fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    from vr_game_sim.constants import EFFECT_NAME_DISARM_DEBUFF
    disarm = EffectInstance(uuid.uuid4(), "d", EffectType.DEBUFF, 1,
                            config={"prevents_basic_attack": True},
                            name=EFFECT_NAME_DISARM_DEBUFF)
    army1.active_effects.append(disarm)

    # Army tries to basic attack - blocked by disarm, no base rage
    sim._calculate_and_log_attack(army1, army2, is_counter=False)

    assert army1.current_rage == 0
    assert not army1.base_rage_awarded_this_round


def test_base_rage_granted_when_hero2_silenced():
    """Hero2 rage skill fires (Hero1 not); army gets base rage from basic attack."""
    hero1 = Hero("H1", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    army1 = Army("A1", unit, heroes=[hero1, hero2])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2, fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    army1.current_rage = 1000
    army1.hero2_rage_skill_primed_for_round = sim.round
    silence = EffectInstance(uuid.uuid4(), "s", EffectType.DEBUFF, 1,
                             config={"prevents_rage_skill_cast": True},
                             name=EFFECT_NAME_SILENCE_DEBUFF)
    army1.active_effects.append(silence)

    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)
    # Hero1 rage skill did not fire; army1 basic attacks and gets base rage
    sim._calculate_and_log_attack(army1, army2, is_counter=False)

    assert army1.current_rage == 1100
    assert army1.base_rage_awarded_this_round


def test_hero2_rage_skill_requeues_while_silenced():
    hero1 = Hero("H1", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    army1 = Army("A1", unit, heroes=[hero1, hero2])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    sim.round = 1
    army1.army_round = sim.round

    army1.current_rage = 1000
    army1.hero2_rage_skill_primed_for_round = sim.round
    silence = EffectInstance(
        uuid.uuid4(),
        "s",
        EffectType.DEBUFF,
        2,
        config={"prevents_rage_skill_cast": True},
        name=EFFECT_NAME_SILENCE_DEBUFF,
    )
    army1.active_effects.append(silence)

    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)
    assert army1.hero2_rage_skill_primed_for_round == 2

    army1.army_round += 1
    sim.round += 1
    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)
    assert army1.hero2_rage_skill_primed_for_round == 3

    army1.active_effects.clear()
    army1.army_round += 1
    sim.round += 1
    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)
    assert army1.hero2_rage_skill_primed_for_round is None


def test_rage_skill_resets_to_round_gain():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1

    army1.current_rage = 1050
    army1.hero1_rage_skill_queued_this_round = True

    aura = EffectInstance(
        uuid.uuid4(),
        "fs",
        EffectType.CUSTOM_SKILL_EFFECT,
        duration=30,
        config={"rage_per_round": 75, "start_rage_gain_round": 1, "end_rage_gain_round": 31},
        name=EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
    )
    army1.active_effects.append(aura)

    army1.process_periodic_effects("start_of_round", opponent=army2)

    sim._execute_rage_skills(army1, army2)

    # On trigger round, no rage from any source (including aura); reset to 0
    assert army1.current_rage == 0


def test_hero2_rage_skill_primes_for_two_round_delay():
    hero1 = Hero("H1", [], ["base_skill_snakes_frenzy", "rage_skill_ruling_trial"], [], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], ["base_skill_snakes_frenzy", "rage_skill_ruling_trial"], [], SKILL_REGISTRY_GLOBAL)
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero1, hero2])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mode="arena", fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.current_rage = 1000
    army1.hero1_rage_skill_queued_this_round = True
    sim._execute_rage_skills(army1, army2)

    assert army1.hero2_rage_skill_primed_for_round == 2


def test_hero2_rage_skill_does_not_reset_rage():
    hero1 = Hero("H1", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero1, hero2])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    sim.round = 1
    army1.current_rage = 1500
    army1.hero2_rage_skill_primed_for_round = sim.round
    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)

    assert army1.current_rage == 1500


def test_fairness_rage_skips_base_rage_for_stronger_army_round_one():
    """With fairness rage on, the stronger army gets no base rage on round 1 when basic attacking."""
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10, initial_atk_modifier=0.5), heroes=[])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2, fairness_rage_enabled=True)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    sim._calculate_and_log_attack(army1, army2, is_counter=False)
    sim._calculate_and_log_attack(army2, army1, is_counter=False)

    # Army1 (stronger) should NOT get base rage on round 1; army2 (weaker) should
    assert army1.current_rage == 0
    assert army2.current_rage == 100
    assert army2.base_rage_awarded_this_round


def test_fairness_rage_disabled_grants_base_rage_to_both():
    """With fairness rage off, both armies get base rage when they basic attack on round 1."""
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10, initial_atk_modifier=0.5), heroes=[])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2, fairness_rage_enabled=False)
    sim.round = 1
    army1.army_round = army2.army_round = 1
    army1.simulator = army2.simulator = sim

    sim._calculate_and_log_attack(army1, army2, is_counter=False)
    sim._calculate_and_log_attack(army2, army1, is_counter=False)

    assert army1.current_rage == 100
    assert army2.current_rage == 100


def test_rage_skill_absorbed_damage_still_triggers_reaction():
    attacker_hero = Hero(
        "Attacker",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        ["base_skill_holy_enlightenment"],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    defender_hero = Hero(
        "Defender",
        ["talent_tit_for_tat", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    attacker = Army("Attacker", Unit("pikemen", 5, initial_count=10), heroes=[attacker_hero])
    defender = Army("Defender", Unit("pikemen", 5, initial_count=10), heroes=[defender_hero])
    sim = GameSimulator(attacker, defender, mode="arena")
    sim.round = 1

    shield = EffectInstance(
        uuid.uuid4(),
        "test_shield",
        EffectType.SHIELD,
        duration=1,
        magnitude=1_000_000,
        name="Test Shield",
    )
    defender.active_effects.append(shield)
    defender.started_round_with_active_shield = True

    attacker.current_rage = 1000
    attacker.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(attacker, defender)

    assert defender.pending_hp_damage_this_round == 0
    assert defender.skill_trigger_counts.get("talent_tit_for_tat") == 1
    assert attacker.pending_hp_damage_this_round > 0
