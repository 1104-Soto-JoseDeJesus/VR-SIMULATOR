import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from vr_game_sim.gui_main import SlowSimTab


def _minimal_setup():
    return {
        "side1": [
            {
                "army_name": "A1",
                "unit_type": "infantry",
                "tier": 5,
                "count": 100,
                "atk_mod": 0.0,
                "def_mod": 0.0,
                "hp_mod": 0.0,
                "heroes": [],
                "grid_pos": [0, 0],
            }
        ],
        "side2": [
            {
                "army_name": "B1",
                "unit_type": "infantry",
                "tier": 5,
                "count": 100,
                "atk_mod": 0.0,
                "def_mod": 0.0,
                "hp_mod": 0.0,
                "heroes": [],
                "grid_pos": [0, 0],
            }
        ],
    }


def test_slow_simulation_runs_without_crashing():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class DummyArenaTab:
        def _build_setup(self):
            return _minimal_setup()

    tab = SlowSimTab(DummyArenaTab())
    tab.start_simulation()
    tab.timer.stop()
    assert tab.rounds, "No rounds were generated"
