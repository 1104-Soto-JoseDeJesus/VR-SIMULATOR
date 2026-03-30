import copy
import random
import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, DoTType, StatType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.constants import EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.base_skill_handlers import handle_base_skill_zeal
from vr_game_sim.skill_logic.talent_handlers import handle_talent_fearless_pursuit


def _start_round(sim: GameSimulator) -> None:
    sim.round += 1
    sim.army1.pending_hp_damage_this_round = 0.0
    sim.army1.pending_hp_healing_this_round = 0.0
    sim.army2.pending_hp_damage_this_round = 0.0
    sim.army2.pending_hp_healing_this_round = 0.0
    for army in (sim.army1, sim.army2):
        if army.effects_to_activate_next_round:
            army.upcoming_effects.extend(army.effects_to_activate_next_round)
            army.effects_to_activate_next_round.clear()
        army.activate_queued_effects()
        army.decrement_effect_durations()
    for army, opponent in ((sim.army1, sim.army2), (sim.army2, sim.army1)):
        army.activate_queued_effects()
        army.process_periodic_effects("start_of_round", opponent=opponent)
        army.activate_queued_effects()


def _basic_armies():
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    return army1, army2, sim


def test_poison_dot_cleansed_as_debuff(monkeypatch):
    army1, army2, sim = _basic_armies()
    poison = EffectInstance(
        uuid.uuid4(),
        "s",
        EffectType.DAMAGE_OVER_TIME,
        1,
        config={"dot_type": DoTType.POISON},
    )
    army1.active_effects.append(poison)
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["base_skill_zeal"])
    skill_def["config"]["debuff_removal_chance"] = 1.0
    skill_def["config"]["damage_chance"] = 0.0
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_base_skill_zeal(army1, army2, skill_def, None, sim)
    assert poison in army1.active_effects
    _start_round(sim)
    assert poison not in army1.active_effects


def test_zeal_cleanse_schedules_harmful_stat_mod(monkeypatch):
    army1, army2, sim = _basic_armies()
    attack_down = EffectInstance(
        uuid.uuid4(),
        "test_skill",
        EffectType.STAT_MOD,
        2,
        magnitude=-0.15,
        config={"stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER},
        name="TestAttackDown",
    )
    assert attack_down.is_harmful_for_target()
    army1.active_effects.append(attack_down)
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["base_skill_zeal"])
    skill_def["config"]["debuff_removal_chance"] = 1.0
    skill_def["config"]["damage_chance"] = 0.0
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_base_skill_zeal(army1, army2, skill_def, None, sim)
    pending = [
        e
        for e in army1.effects_to_activate_next_round
        if e.name == EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE
    ]
    assert len(pending) == 1
    assert attack_down.id in pending[0].config["debuff_ids_to_remove"]
    _start_round(sim)
    assert attack_down not in army1.active_effects
    assert not any(e.id == attack_down.id for e in army1.active_effects)


def test_dot_counts_as_debuff_for_condition(monkeypatch):
    army1, army2, sim = _basic_armies()
    bleed = EffectInstance(
        uuid.uuid4(),
        "s",
        EffectType.DAMAGE_OVER_TIME,
        1,
        config={"dot_type": DoTType.BLEED},
    )
    army2.active_effects.append(bleed)
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["talent_fearless_pursuit"])
    skill_def["config"]["damage_factor"] = 100
    skill_def["config"]["alt_damage_factor"] = 200
    recorded = {}

    def fake_calc(trig, opp, factor, **kwargs):
        recorded["factor"] = factor
        return 0, 0, 0, 0, []

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_talent_fearless_pursuit(army1, army2, skill_def, None, sim)
    assert recorded.get("factor") == 200


def test_no_debuff_uses_base_damage(monkeypatch):
    army1, army2, sim = _basic_armies()
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["talent_fearless_pursuit"])
    skill_def["config"]["damage_factor"] = 150
    skill_def["config"]["alt_damage_factor"] = 325
    recorded = {}

    def fake_calc(trig, opp, factor, **kwargs):
        recorded["factor"] = factor
        return 0, 0, 0, 0, []

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_talent_fearless_pursuit(army1, army2, skill_def, None, sim)
    assert recorded.get("factor") == 150
