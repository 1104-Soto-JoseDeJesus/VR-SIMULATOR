import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets

from vr_game_sim.gui_main import MainWindow

# Create a single QApplication instance for the test module
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

def test_round_view_displays_skill_kills():
    window = MainWindow()
    rounds = [
        {
            "round": 1,
            "combat_actions": [],
            "skill_triggers": {
                "Army1": [
                    {
                        "skill_name": "Fireball",
                        "effect_description": "Burns enemy",
                        "damage_done_hp": 100,
                        "potential_kills": 2,
                    }
                ]
            },
            "active_effects": [],
        }
    ]
    window._populate_round_tree(rounds)
    round_item = window.output_tree.topLevelItem(0)
    army_item = round_item.child(0)
    skill_item = army_item.child(0)
    assert "Kills 2" in skill_item.text(0)
    window.close()
