import pytest

from vr_game_sim.hero_definition import Hero
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.enums import SkillTriggerType, SkillType, PluginSkillLabel


def _reset_round_state(army: Army) -> None:
    army.triggered_skills_this_round.clear()
    army.skill_trigger_counts_this_round.clear()
    army.skill_triggers_against_this_round.clear()
    army.pending_hp_damage_this_round = 0


def _logic_factory(log: list[tuple[str, int]], label: str):
    def _handler(triggering_army: Army, _target: Army, _skill_def, _event_data, _simulator):
        log.append((label, triggering_army.army_round))
        return True, []

    return _handler


@pytest.fixture
def skill_registry_guard():
    original_values: dict[str, dict] = {}
    yield original_values
    for skill_id, original in original_values.items():
        if original is None:
            SKILL_REGISTRY_GLOBAL.pop(skill_id, None)
        else:
            SKILL_REGISTRY_GLOBAL[skill_id] = original


def _register_skill(skill_def: dict, originals: dict[str, dict]) -> None:
    skill_id = skill_def["id"]
    if skill_id not in originals:
        originals[skill_id] = SKILL_REGISTRY_GLOBAL.get(skill_id)
    SKILL_REGISTRY_GLOBAL[skill_id] = skill_def


def _build_army_with_hero(hero_skill_ids: list[str]) -> Army:
    hero = Hero(
        "Hero",
        ["dummy_talent_empty"] * 3,
        hero_skill_ids,
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    return Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero])


def test_default_cooldowns_apply_per_category(skill_registry_guard):
    log: list[tuple[str, int]] = []
    hero_skill = {
        "id": "hero_cd_skill",
        "name": "Hero Cooldown",
        "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "config": {"cooldown_rounds": 3},
        "logic_handler": _logic_factory(log, "hero"),
    }
    plugin_skill = {
        "id": "plugin_cd_skill",
        "name": "Plugin Cooldown",
        "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"cooldown_rounds": 3},
        "logic_handler": _logic_factory(log, "plugin"),
    }
    _register_skill(hero_skill, skill_registry_guard)
    _register_skill(plugin_skill, skill_registry_guard)

    army1 = _build_army_with_hero([hero_skill["id"], plugin_skill["id"]])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)

    for round_no in (1, 2):
        army1.army_round = round_no
        sim.round = round_no
        _reset_round_state(army1)
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)

    assert log == [("hero", 1), ("plugin", 1)]


def test_plugin_cooldowns_can_be_disabled_independently(skill_registry_guard):
    log: list[tuple[str, int]] = []
    hero_skill_id = "hero_cd_skill_plugin_toggle"
    plugin_skill_id = "plugin_cd_skill_toggle"
    hero_skill = {
        "id": hero_skill_id,
        "name": "Hero Cooldown",
        "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "config": {"cooldown_rounds": 2},
        "logic_handler": _logic_factory(log, "hero"),
    }
    plugin_skill = {
        "id": plugin_skill_id,
        "name": "Plugin Cooldown",
        "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"cooldown_rounds": 2},
        "logic_handler": _logic_factory(log, "plugin"),
    }
    _register_skill(hero_skill, skill_registry_guard)
    _register_skill(plugin_skill, skill_registry_guard)

    army1 = _build_army_with_hero([hero_skill_id, plugin_skill_id])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, plugin_cooldowns_enabled=False)

    for round_no in (1, 2):
        army1.army_round = round_no
        sim.round = round_no
        _reset_round_state(army1)
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)

    assert log.count(("hero", 1)) == 1
    assert log.count(("hero", 2)) == 0
    assert log.count(("plugin", 1)) == 1
    assert log.count(("plugin", 2)) == 1


def test_gem_cooldowns_toggle_independently(skill_registry_guard):
    log: list[tuple[str, int]] = []
    gem_skill = {
        "id": "gem_cd_skill",
        "name": "Gem Cooldown",
        "type": SkillType.GEM_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "config": {"cooldown_rounds": 2},
        "logic_handler": _logic_factory(log, "gem"),
    }
    _register_skill(gem_skill, skill_registry_guard)

    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[])
    army1.set_gem_skills({"friggs_agate": gem_skill["id"]})
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, gem_cooldowns_enabled=False)

    for round_no in (1, 2):
        army1.army_round = round_no
        sim.round = round_no
        _reset_round_state(army1)
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)

    assert log.count(("gem", 1)) == 1
    assert log.count(("gem", 2)) == 1


def test_mount_cooldowns_can_be_disabled(skill_registry_guard):
    log: list[tuple[str, int]] = []
    mount_skill = {
        "id": "mount_cd_skill",
        "name": "Mount Cooldown",
        "type": "MOUNT_SKILL",
        "source": "mount",
        "trigger": SkillTriggerType.ON_BASIC_ATTACK,
        "trigger_chance": 1.0,
        "config": {"cooldown_rounds": 2},
        "logic_handler": _logic_factory(log, "mount"),
    }
    _register_skill(mount_skill, skill_registry_guard)

    hero = Hero(
        "Rider",
        ["dummy_talent_empty"] * 3,
        [mount_skill["id"]],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mount_cooldowns_enabled=False)

    for round_no in (1, 2):
        army1.army_round = round_no
        sim.round = round_no
        _reset_round_state(army1)
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_BASIC_ATTACK)

    assert log.count(("mount", 1)) == 1
    assert log.count(("mount", 2)) == 1


def test_counterattack_cooldown_respected_with_hero_toggle_disabled(skill_registry_guard):
    log: list[tuple[str, int]] = []
    counter_skill = {
        "id": "counter_cd_skill",
        "name": "Counter Cooldown",
        "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK,
        "trigger_chance": 1.0,
        "config": {"cooldown_rounds": 1},
        "logic_handler": _logic_factory(log, "counter"),
    }
    _register_skill(counter_skill, skill_registry_guard)

    army1 = _build_army_with_hero([counter_skill["id"]])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, hero_cooldowns_enabled=False)

    army1.army_round = 1
    sim.round = 1
    _reset_round_state(army1)

    for _ in range(3):
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_COUNTER_ATTACK)

    army1.army_round = 2
    sim.round = 2
    _reset_round_state(army1)

    for _ in range(2):
        sim._process_skill_triggers(army1, army2, SkillTriggerType.ON_COUNTER_ATTACK)

    assert log.count(("counter", 1)) == 1
    assert log.count(("counter", 2)) == 1


def test_chance_per_round_ignores_cooldown_modifiers(skill_registry_guard):
    log: list[tuple[str, int]] = []

    def _periodic_handler(interval: int):
        def _handler(triggering_army: Army, _target: Army, _skill_def, _event_data, _simulator):
            if triggering_army.army_round > 0 and triggering_army.army_round % interval == 0:
                log.append(("mount", triggering_army.army_round))
                return True, []
            return False, []

        return _handler

    periodic_skill = {
        "id": "mount_chance_cd_skill",
        "name": "Crippling Strike",
        "type": "MOUNT_SKILL",
        "source": "mount",
        "trigger": SkillTriggerType.CHANCE_PER_ROUND,
        "trigger_chance": 1.0,
        "config": {"trigger_interval": 6, "cooldown_rounds": 8},
        "logic_handler": _periodic_handler(6),
    }
    _register_skill(periodic_skill, skill_registry_guard)

    hero = Hero(
        "Rider",
        ["dummy_talent_empty"] * 3,
        [periodic_skill["id"]],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2, mount_cooldowns_enabled=True)

    for round_no in range(1, 13):
        army1.army_round = round_no
        sim.round = round_no
        _reset_round_state(army1)
        sim._process_skill_triggers(army1, army2, SkillTriggerType.CHANCE_PER_ROUND)

    assert log == [("mount", 6), ("mount", 12)]
