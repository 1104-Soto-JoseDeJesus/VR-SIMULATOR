import os
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_skill_override_persists_after_reopen():
    _get_app()
    from vr_game_sim.gui_main import ArmyFrame

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
    }

    frame = ArmyFrame(1)
    frame.populate_from_config(cfg)
    saved_cfg = frame.build_config()
    frame2 = ArmyFrame(1)
    frame2.populate_from_config(saved_cfg)
    assert frame2.hero_overrides[1] == cfg["heroes"][0]["skill_overrides"]
