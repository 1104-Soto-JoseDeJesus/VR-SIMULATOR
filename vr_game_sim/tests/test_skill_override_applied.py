import os
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_skill_override_applied_in_arena():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab, ArmyIcon, create_armies_from_data
    from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL

    tab = ArenaTab()

    cfg = {
        "army_name": "OverrideArmy",
        "unit_type": "archers",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [
            {
                "hero_name_or_preset": "Tester",
                "talent_ids": ["talent_shield_of_resistance"],
                "base_skill_ids": [],
                "plugin_skill_ids": [],
                "skill_overrides": {
                    "talent_shield_of_resistance": {"trigger_chance": 1.0}
                },
            }
        ],
        "team": "red",
        "speed": 50.0,
    }

    # Default chance should be less than our override
    assert SKILL_REGISTRY_GLOBAL["talent_shield_of_resistance"]["trigger_chance"] == 0.20

    army = create_armies_from_data([cfg])[0]
    pos = tab.slot_coords["team1"][0]
    icon = ArmyIcon(
        os.path.join(os.path.dirname(__file__), "..", "Icons", "archers.png"),
        None,
        1.0,
        army_name=army.name,
        team="red",
        max_size=tab._icon_size,
    )
    icon.setPos(*pos)
    tab.scene.addItem(icon)
    tab._icons[army.name] = icon
    tab._slot_army[("team1", 0)] = {"army": army, "team": "red", "speed": 50.0, "config": cfg}

    tab._run_arena()
    hero = tab.engine._armies[army.name].army.heroes[0]
    skill = [s for s in hero.skills if s["id"] == "talent_shield_of_resistance"][0]
    assert skill["trigger_chance"] == 1.0
