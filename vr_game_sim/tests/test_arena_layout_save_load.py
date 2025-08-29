import os
import json
from PyQt6 import QtWidgets


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_save_and_load_layout(tmp_path, monkeypatch):
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab, ArmyIcon, create_armies_from_data

    tab = ArenaTab()
    # Redirect setups directory and saved armies file to the temporary path
    tab._setups_dir = str(tmp_path)
    tab.saved_armies_file = str(tmp_path / "saved_armies.json")

    cfg1 = {
        "army_name": "Alpha",
        "unit_type": "archers",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }
    cfg2 = {
        "army_name": "Beta",
        "unit_type": "infantry",
        "tier": 5,
        "count": 10,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }
    with open(tab.saved_armies_file, "w", encoding="utf-8") as fh:
        json.dump({"Alpha": cfg1, "Beta": cfg2}, fh)

    # Manually place armies
    army1 = create_armies_from_data([cfg1])[0]
    pos1 = tab.slot_coords["team1"][0]
    tab.engine.add_army(army1, "red", position=pos1, speed=50.0)
    icon1 = ArmyIcon(os.path.join(os.path.dirname(__file__), "..", "Icons", "archers.png"), None, 1.0, army_name=army1.name, team="red", max_size=tab._icon_size)
    icon1.setPos(*pos1)
    tab.scene.addItem(icon1)
    tab._icons[army1.name] = icon1
    tab._slot_army[("team1", 0)] = army1.name
    tab._army_slot[army1.name] = ("team1", 0, 0)

    army2 = create_armies_from_data([cfg2])[0]
    pos2 = tab.slot_coords["team2"][4]
    tab.engine.add_army(army2, "blue", position=pos2, speed=50.0)
    icon2 = ArmyIcon(os.path.join(os.path.dirname(__file__), "..", "Icons", "infantry.png"), None, 1.0, army_name=army2.name, team="blue", max_size=tab._icon_size)
    icon2.setPos(*pos2)
    tab.scene.addItem(icon2)
    tab._icons[army2.name] = icon2
    tab._slot_army[("team2", 4)] = army2.name
    tab._army_slot[army2.name] = ("team2", 1, 1)

    layout_file = tmp_path / "layout.json"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(layout_file), "json"))
    tab._save_layout()

    with open(layout_file, "r", encoding="utf-8") as fh:
        saved = json.load(fh)
    assert {entry["army_name"] for entry in saved} == {"Alpha", "Beta"}

    # Clear and reload
    tab._refresh_arena()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(layout_file), "json"))
    tab._load_layout()

    assert tab._slot_army[("team1", 0)] == "Alpha"
    assert tab._slot_army[("team2", 4)] == "Beta"
