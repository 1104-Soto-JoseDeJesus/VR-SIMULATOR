from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.enums import SkillType, SkillTriggerType
from vr_game_sim.skill_logic.utility_skill_handlers import handle_generic_single_damage_skill
from vr_game_sim.skill_logic.talent_handlers import _get_army_round


def make_basic_army(name: str):
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit)


def make_rage_army(name: str) -> Army:
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def make_round_skill_army(name: str) -> Army:
    hero = Hero("Tester", ["talent_godly_wrath"], [], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def make_first_strike_army(name: str) -> Army:
    hero = Hero("Tester", [], [], ["plugin_first_strike"], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def test_rage_skill_executes_in_battlefield():
    engine = BattlefieldEngine()
    attacker = make_rage_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    attacker.current_rage = 1050

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1 – rage skill triggers immediately at start of round

    assert attacker.current_rage == 0
    assert attacker.rage_added_this_round == 0
    assert attacker.skill_trigger_counts.get("base_skill_snakes_frenzy", 0) == 1
    assert defender.current_troop_count < 1000


def test_chance_per_round_skill_triggers():
    engine = BattlefieldEngine()
    attacker = make_round_skill_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1
    engine.tick(1.0)  # round 2

    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1


def test_interval_skill_uses_attacker_round():
    engine = BattlefieldEngine()

    original = SKILL_REGISTRY_GLOBAL.get("talent_interval_test")
    def interval_handler(trig_army, opp_army, sk_def, ev_data, sim):
        interval = sk_def.get("config", {}).get("trigger_interval", 1)
        if _get_army_round(trig_army, sim) > 0 and _get_army_round(trig_army, sim) % interval == 0:
            return handle_generic_single_damage_skill(trig_army, opp_army, sk_def, ev_data, sim)
        return False, []

    SKILL_REGISTRY_GLOBAL["talent_interval_test"] = {
        "id": "talent_interval_test",
        "name": "Interval Test",
        "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND,
        "logic_handler": interval_handler,
        "config": {"damage_factor": 1.0, "trigger_interval": 2},
    }

    try:
        hero = Hero("Tester", ["talent_interval_test"], [], [], SKILL_REGISTRY_GLOBAL)
        delayed = Army("A", Unit("pikemen", 5, initial_count=1000), heroes=[hero])
        pioneer = make_basic_army("P")
        defender = make_basic_army("B")
        engine.add_army(pioneer, "red", position=(0, 0), speed=0)
        engine.add_army(defender, "blue", position=(2, 0), speed=0)
        engine.add_army(delayed, "red", position=(0, 0), speed=0)

        engine.tick(0.3)
        engine.engage("P", "B")
        engine.tick(0.7)  # round 1 for P/B
        engine.tick(1.0)  # round 2 for P/B
        engine.tick(0.2)
        engine.engage("A", "B")  # delayed attacker joins next round
        engine.tick(0.8)  # round 3 for P/B, round 1 for A

        assert delayed.army_round == 1
        assert delayed.skill_trigger_counts.get("talent_interval_test", 0) == 0

        engine.tick(1.0)  # round 4 for P/B, round 2 for A

        assert delayed.army_round == 2
        assert delayed.skill_trigger_counts.get("talent_interval_test", 0) == 1
    finally:
        if original is not None:
            SKILL_REGISTRY_GLOBAL["talent_interval_test"] = original
        else:
            del SKILL_REGISTRY_GLOBAL["talent_interval_test"]


def test_round_dependent_skill_resets_after_idle():
    engine = BattlefieldEngine()
    attacker = make_round_skill_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1
    engine.tick(1.0)  # round 2 triggers once
    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1

    engine.set_direct_target("A", None)
    engine.tick(0.8)  # idle but below reset threshold
    engine.tick(0.2)  # exceed threshold and reset rounds/rage
    assert attacker.skill_last_triggered_round == {}
    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1
    engine.engage("A", "B")
    engine.tick(1.0)  # new round 1
    engine.tick(1.0)  # new round 2

    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 2


def test_round_dependent_skill_resets_after_idle_in_arena():
    engine = ArenaEngine()
    attacker = make_round_skill_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1
    engine.tick(1.0)  # round 2 triggers once
    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1

    engine.set_direct_target("A", None)
    engine.tick(0.8)
    engine.tick(0.2)
    assert attacker.skill_last_triggered_round == {}
    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 1
    engine.engage("A", "B")
    engine.tick(1.0)
    engine.tick(1.0)

    assert attacker.skill_trigger_counts.get("talent_godly_wrath", 0) == 2


def test_rage_skill_blocks_base_rage_in_arena():
    engine = ArenaEngine()
    attacker = make_rage_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    attacker.current_rage = 1050

    engine.engage("A", "B")
    engine.tick(1.0)  # round 1 – rage skill triggers at start, blocks base rage

    assert attacker.current_rage == 0
    assert attacker.rage_added_this_round == 0


def test_no_base_rage_on_trigger_round():
    engine = ArenaEngine()
    attacker = make_rage_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    attacker.current_rage = 1050

    engine.engage("A", "B")
    engine.tick(1.0)

    assert attacker.current_rage == 0
    assert not attacker.base_rage_awarded_this_round


def test_first_strike_resets_after_idle():
    engine = BattlefieldEngine()
    attacker = make_first_strike_army("A")
    defender = make_basic_army("B")
    engine.add_army(attacker, "red", position=(0, 0), speed=0)
    engine.add_army(defender, "blue", position=(2, 0), speed=0)

    engine.engage("A", "B")
    engine.tick(1.0)
    assert attacker.skill_trigger_counts.get("plugin_first_strike", 0) == 1

    engine.set_direct_target("A", None)
    engine.tick(0.8)
    engine.tick(0.2)
    assert attacker.skill_trigger_counts.get("plugin_first_strike", 0) == 1

    engine.engage("A", "B")
    engine.tick(1.0)
    assert attacker.skill_trigger_counts.get("plugin_first_strike", 0) == 2


def test_defender_attacks_even_if_targeting_other():
    engine = BattlefieldEngine()
    army_a = make_basic_army("A")
    army_b = make_basic_army("B")
    army_c = make_basic_army("C")

    engine.add_army(army_a, "red", position=(100, 0), speed=0)
    engine.add_army(army_b, "red", position=(0, 0), speed=0)
    engine.add_army(army_c, "blue", position=(2, 0), speed=0)

    engine.engage("A", "C")
    engine.engage("B", "C")
    engine.tick(1.0)

    assert army_b.current_troop_count < 1000

