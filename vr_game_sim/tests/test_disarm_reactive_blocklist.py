import random

from vr_game_sim.army_composition import Army
from vr_game_sim.constants import EFFECT_NAME_DISARM_DEBUFF
from vr_game_sim.enums import SkillTriggerType, EffectType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def _make_army_with_skill_id(skill_id: str, slot: str) -> Army:
    talent_ids = []
    base_ids = []
    plugin_ids = []
    mount_ids = []
    if slot == "talent":
        talent_ids = [skill_id]
    elif slot == "base":
        base_ids = [skill_id]
    elif slot == "plugin":
        plugin_ids = [skill_id]
    elif slot == "mount":
        mount_ids = [skill_id]
    else:
        raise ValueError(f"Unknown skill slot '{slot}'")

    hero = Hero(
        "H",
        talent_ids,
        base_ids,
        plugin_ids,
        SKILL_REGISTRY_GLOBAL,
        mount_skill_ids=mount_ids,
    )
    return Army("Defender", Unit("pikemen", 5, initial_count=10), heroes=[hero])


def _apply_disarm(army: Army, sim: GameSimulator) -> None:
    sim.round = 1
    army.army_round = 1
    data = {
        "effect_type": EffectType.DEBUFF,
        "name": EFFECT_NAME_DISARM_DEBUFF,
        "duration": 1,
    }
    created = army._create_and_add_single_effect(data, "test_disarm", army, army, None)
    assert created is not None


def _assert_blocked_when_attacker_disarmed(skill_id: str, slot: str, monkeypatch) -> None:
    defender = _make_army_with_skill_id(skill_id, slot)
    attacker = Army("Attacker", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(defender, attacker)
    defender.army_round = attacker.army_round = 1
    sim.round = 1

    _apply_disarm(attacker, sim)

    recorded = []

    def fake_calc(source, target, factor, **kwargs):
        recorded.append((target.name, factor))
        return 0, 0, 0, 0, []

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    sim._process_skill_triggers(
        defender,
        attacker,
        SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
        event_data={"attacking_army_for_tit_for_tat": attacker},
    )

    assert recorded == []


def test_disarm_blocks_reactive_hit_by_basic_attack_plugin(monkeypatch):
    _assert_blocked_when_attacker_disarmed("plugin_rapid_attack", "plugin", monkeypatch)


def test_disarm_blocks_reactive_hit_by_basic_attack_talent(monkeypatch):
    _assert_blocked_when_attacker_disarmed("talent_sacred_counter", "talent", monkeypatch)


def test_disarm_blocks_reactive_hit_by_basic_attack_mount(monkeypatch):
    _assert_blocked_when_attacker_disarmed("mount_pincer_strike", "mount", monkeypatch)
