import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from vr_game_sim.realtime_battle_widget import RealTimeBattleWidget


def _sample_config():
    return {
        "army_name": "Army",
        "unit_type": "pikemen",
        "tier": 5,
        "count": 100,
        "atk_mod": 0,
        "def_mod": 0,
        "hp_mod": 0,
        "unrevivable_ratio": 0.5,
        "heroes": [
            {
                "hero_name_or_preset": "Artur",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": [],
            },
            {
                "hero_name_or_preset": "Bjorn",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": [],
            },
        ],
    }


def test_save_and_load(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    army_file = tmp_path / "armies.json"
    widget = RealTimeBattleWidget(army_file=army_file)
    widget._add_army_from_config(_sample_config(), team=1)
    widget._save_armies()
    assert army_file.exists()
    widget._refresh_battlefield()
    assert not widget.armies
    widget._load_armies()
    assert len(widget.armies) == 1
    item = widget.armies[0]["item"]
    height = item.main_item.pixmap().height()
    assert item.health_fg.rect().height() == height
    item.set_troop_count(50)
    assert item.health_fg.rect().height() == height / 2

