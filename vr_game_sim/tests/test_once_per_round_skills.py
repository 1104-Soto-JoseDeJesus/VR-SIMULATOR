import random

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.army_composition import Army
from vr_game_sim.constants import EFFECT_NAME_MANIACAL_HOT
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType
from vr_game_sim.skill_logic.talent_handlers import handle_talent_maniacal


def _start_round(sim: GameSimulator) -> None:
    sim.round += 1
    sim.army1.rage_added_this_round = 0.0
    sim.army2.rage_added_this_round = 0.0
    sim.army1.shield_hp_gained_this_round = 0.0
    sim.army2.shield_hp_gained_this_round = 0.0
    sim.army1.pending_hp_damage_this_round = 0.0
    sim.army1.pending_hp_healing_this_round = 0.0
    sim.army2.pending_hp_damage_this_round = 0.0
    sim.army2.pending_hp_healing_this_round = 0.0
    sim.round_combat_actions_log.clear()
    sim.round_skill_triggers_log = {sim.army1.name: [], sim.army2.name: []}
    for army in (sim.army1, sim.army2):
        army.triggered_skills_this_round.clear()
        army.on_receiving_healing_rolls_this_round.clear()
        army.skill_trigger_counts_this_round.clear()
        army.skill_triggers_against_this_round.clear()
        army.maniacal_hot_triggered_this_round = False
        army.healing_hymn_triggered_this_round = False
        army.forceful_ambush_shield_triggered_this_round = False
        army.base_rage_awarded_this_round = False


def test_healing_hymn_resets_each_round_simulator(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False)

    _start_round(sim)
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    dmg_first = enemy.pending_hp_damage_this_round
    assert dmg_first > 0
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == dmg_first

    _start_round(sim)
    assert not army.healing_hymn_triggered_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round > 0


def test_healing_hymn_resets_each_round_battlefield_engine(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])

    engine = BattlefieldEngine()
    monkeypatch.setattr(GameSimulator, "_calculate_and_log_attack", lambda self, a, b, is_counter=False: (0, 0, 0, 0))
    engine.add_army(army, "T1")
    engine.add_army(enemy, "T2")
    engine.engage("A", "E")
    engine.tick(1.0)

    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    dmg_first = enemy.pending_hp_damage_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == dmg_first
    assert dmg_first > 0
    assert army.healing_hymn_triggered_this_round

    engine.tick(1.0)
    assert not army.healing_hymn_triggered_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert army.healing_hymn_triggered_this_round


def test_on_heal_rolls_once_per_round_by_default(monkeypatch):
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False, multi_heal_trig_enabled=False)

    _start_round(sim)
    rolls = iter([0.9, 0.0])
    monkeypatch.setattr(random, "random", lambda: next(rolls))
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    army.calculate_and_add_pending_healing(1000.0, army, enemy)

    assert enemy.pending_hp_damage_this_round == 0
    assert not army.healing_hymn_triggered_this_round


def test_multi_heal_trig_allows_more_rolls_but_one_trigger(monkeypatch):
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False, multi_heal_trig_enabled=True)

    _start_round(sim)
    rolls = iter([0.9, 0.0, 0.0])
    monkeypatch.setattr(random, "random", lambda: next(rolls))
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == 0

    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    dmg_after_second = enemy.pending_hp_damage_this_round
    assert dmg_after_second > 0
    assert army.healing_hymn_triggered_this_round

    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == dmg_after_second


def test_maniacal_applies_one_hot_per_round(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["talent_maniacal"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False)

    _start_round(sim)
    skill_def = SKILL_REGISTRY_GLOBAL["talent_maniacal"]

    happened_first, logs_first = handle_talent_maniacal(army, enemy, skill_def, None, sim)
    happened_second, logs_second = handle_talent_maniacal(army, enemy, skill_def, None, sim)

    hot_queue = [eff for eff in army.effects_to_activate_next_round if eff.name == EFFECT_NAME_MANIACAL_HOT]

    assert happened_first
    assert logs_first
    assert not happened_second
    assert not logs_second
    assert len(hot_queue) == 1

    _start_round(sim)
    army.effects_to_activate_next_round.clear()

    happened_third, _ = handle_talent_maniacal(army, enemy, skill_def, None, sim)
    new_hot_queue = [eff for eff in army.effects_to_activate_next_round if eff.name == EFFECT_NAME_MANIACAL_HOT]

    assert happened_third
    assert len(new_hot_queue) == 1


def test_duplicate_counterattack_skills_from_different_heroes_trigger_same_round(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero1 = Hero("H1", [], [], ["talent_blade_counter"], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], [], ["talent_blade_counter"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero1, hero2])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False)

    _start_round(sim)
    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_COUNTER_ATTACK)

    trigger_keys = [key for key in army.triggered_skills_this_round if key.startswith("talent_blade_counter")]
    assert len(trigger_keys) == 2
    assert len(set(trigger_keys)) == 2
    assert army.skill_trigger_counts.get("talent_blade_counter", 0) == 2
