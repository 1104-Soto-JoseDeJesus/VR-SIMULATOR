import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets

import vr_game_sim.gui_main as gui_main
from vr_game_sim.gui_main import MainWindow, ArmyIcon, create_armies_from_data

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_run_batch_generates_figure():
    window = MainWindow()
    tab = window.arena_tab

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

    army1 = create_armies_from_data([cfg1])[0]
    pos1 = tab.slot_coords["team1"][0]
    icon1 = ArmyIcon(
        os.path.join(os.path.dirname(__file__), "..", "Icons", "archers.png"),
        None,
        1.0,
        army_name=army1.name,
        team="red",
        max_size=tab._icon_size,
    )
    icon1.setPos(*pos1)
    tab.scene.addItem(icon1)
    tab._icons[army1.name] = icon1
    tab._slot_army[("team1", 0)] = {
        "army": army1,
        "team": "red",
        "speed": 50.0,
        "config": cfg1,
    }

    army2 = create_armies_from_data([cfg2])[0]
    pos2 = tab.slot_coords["team2"][5]
    icon2 = ArmyIcon(
        os.path.join(os.path.dirname(__file__), "..", "Icons", "infantry.png"),
        None,
        1.0,
        army_name=army2.name,
        team="blue",
        max_size=tab._icon_size,
    )
    icon2.setPos(*pos2)
    tab.scene.addItem(icon2)
    tab._icons[army2.name] = icon2
    tab._slot_army[("team2", 5)] = {
        "army": army2,
        "team": "blue",
        "speed": 50.0,
        "config": cfg2,
    }

    tab._run_batch(count=3)
    pix = window.arena_fig_label.pixmap()
    assert pix is not None and not pix.isNull()
    window.close()


def test_arena_batch_seed_uses_single_process(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    created_pool: dict[str, bool] = {"called": False}

    class _ForbiddenPool:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_pool["called"] = True
            raise AssertionError("Process pool should not be used when seed targeting")

    monkeypatch.setattr(gui_main.concurrent.futures, "ProcessPoolExecutor", _ForbiddenPool)

    def _fake_sim(
        layout_entries: list[dict[str, object]],
        targeting_mode: str,
        simulator_options: dict[str, object],
        seed: int | None,
        *,
        collect_skills: bool = False,
    ) -> tuple[str, dict[str, float], list[dict[str, object]] | None]:
        winner = "red"
        remaining = {str(entry.get("entry_id", "")): float(seed or 0) for entry in layout_entries}
        summary: list[dict[str, object]] | None = [] if collect_skills else None
        return winner, remaining, summary

    monkeypatch.setattr(gui_main, "_simulate_arena_battle", _fake_sim)

    layout_entries = [
        {
            "cfg": {},
            "team": "red",
            "position": (0.0, 0.0),
            "column": 0,
            "row": 0,
            "speed": 50.0,
            "entry_id": "slot",
        }
    ]

    worker = gui_main.ArenaBatchWorker(
        layout_entries,
        runs=2,
        num_workers=2,
        targeting_mode="legacy",
        simulator_options={},
        seed_target={"winner": "red", "remaining": {"slot": 0}},
    )

    worker.run()

    assert not created_pool["called"]
    assert worker.best_match is not None
