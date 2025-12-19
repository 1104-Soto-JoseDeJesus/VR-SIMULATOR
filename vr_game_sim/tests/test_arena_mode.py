import os
import pytest
from PyQt6 import QtWidgets

from vr_game_sim import game_simulator
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.battlefield_engine import ENGAGEMENT_DISTANCE


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_army(name: str, count: int = 1000) -> Army:
    unit = Unit("pikemen", 5, initial_count=count)
    return Army(name, unit)


def test_slot_distances():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab()
    coords1 = tab.slot_coords["team1"]
    coords2 = tab.slot_coords["team2"]

    speed = 50.0
    engage_dist = 4 * speed + ENGAGEMENT_DISTANCE
    back_dist = speed * 2
    lateral = speed * 1.5

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    # horizontal distance between opposing front slots
    assert dist(coords1[1], coords2[1]) == pytest.approx(engage_dist)
    # horizontal distance between front and back slots of same team
    assert dist(coords1[1], coords1[5]) == pytest.approx(back_dist)
    # vertical distance between columns
    assert dist(coords1[0], coords1[1]) == pytest.approx(lateral)


def test_initial_column_targeting():
    engine = ArenaEngine()
    a_left = make_army("A_left")
    a_right = make_army("A_right")
    b_left = make_army("B_left")
    b_right = make_army("B_right")

    layout = {
        "red": [
            {"army": a_left, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_right, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b_left, "position": (0.0, 200.0), "column": 0, "row": 0},
            {"army": b_right, "position": (300.0, 200.0), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    assert engine._armies[a_left.name].direct_target == b_left.name
    assert engine._armies[a_right.name].direct_target == b_right.name
    assert engine._armies[b_left.name].direct_target == a_left.name
    assert engine._armies[b_right.name].direct_target == a_right.name


def test_retarget_when_column_empty():
    engine = ArenaEngine()
    a_left = make_army("A_left")
    a_right = make_army("A_right")
    b_left = make_army("B_left", 1)  # dies quickly
    b_right = make_army("B_right")

    layout = {
        "red": [
            {"army": a_left, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a_right, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b_left, "position": (0.0, ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 0},
            {"army": b_right, "position": (300.0, ENGAGEMENT_DISTANCE * 2), "column": 1, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(20):
        engine.tick(1.0)
        if "B_left" not in engine._armies:
            break

    assert "B_left" not in engine._armies
    assert engine._armies[a_left.name].direct_target == b_right.name


def test_defender_retarget_after_kill():
    engine = ArenaEngine()
    a1 = make_army("A1", 1)  # weak attacker
    a2 = make_army("A2")
    b1 = make_army("B1")

    layout = {
        "red": [
            {"army": a1, "position": (0.0, 0.0), "column": 0, "row": 0},
            {"army": a2, "position": (300.0, 0.0), "column": 1, "row": 0},
        ],
        "blue": [
            {"army": b1, "position": (0.0, ENGAGEMENT_DISTANCE * 2), "column": 0, "row": 0},
        ],
    }

    engine.start_arena_battle(layout)

    for _ in range(20):
        engine.tick(1.0)
        if "A1" not in engine._armies:
            break

    assert "A1" not in engine._armies
    assert engine._armies[b1.name].direct_target == a2.name


def test_four_column_pairing_and_fallback():
    engine = ArenaEngine()

    a0f = make_army("A0F")
    a0b = make_army("A0B")
    a1f = make_army("A1F")
    a1b = make_army("A1B")
    a2b = make_army("A2B")
    a3f = make_army("A3F")
    a3b = make_army("A3B")

    b0f = make_army("B0F")
    b0b = make_army("B0B")
    b1f = make_army("B1F")
    b2f = make_army("B2F")
    b2b = make_army("B2B")

    r_front_y = 0.0
    r_back_y = -ENGAGEMENT_DISTANCE * 2
    b_front_y = ENGAGEMENT_DISTANCE * 2
    b_back_y = ENGAGEMENT_DISTANCE * 4

    layout = {
        "red": [
            {"army": a0f, "position": (0.0, r_front_y), "index": 0},
            {"army": a0b, "position": (0.0, r_back_y), "index": 4},
            {"army": a1f, "position": (300.0, r_front_y), "index": 1},
            {"army": a1b, "position": (300.0, r_back_y), "index": 5},
            {"army": a2b, "position": (600.0, r_back_y), "index": 6},
            {"army": a3f, "position": (900.0, r_front_y), "index": 3},
            {"army": a3b, "position": (900.0, r_back_y), "index": 7},
        ],
        "blue": [
            {"army": b0f, "position": (0.0, b_front_y), "index": 0},
            {"army": b0b, "position": (0.0, b_back_y), "index": 4},
            {"army": b1f, "position": (300.0, b_front_y), "index": 1},
            {"army": b2f, "position": (600.0, b_front_y), "index": 2},
            {"army": b2b, "position": (600.0, b_back_y), "index": 6},
        ],
    }

    engine.start_arena_battle(layout)

    # Column 0: full pairing
    assert engine._armies[a0f.name].direct_target == b0f.name
    assert engine._armies[a0b.name].direct_target == b0f.name
    assert engine._armies[b0f.name].direct_target == a0f.name
    assert engine._armies[b0b.name].direct_target == a0f.name

    # Column 1: red back falls back to blue front
    assert engine._armies[a1f.name].direct_target == b1f.name
    assert engine._armies[a1b.name].direct_target == b1f.name
    assert engine._armies[b1f.name].direct_target == a1f.name

    # Column 2: blue front falls back to red back
    assert engine._armies[a2b.name].direct_target == b2f.name
    assert engine._armies[b2b.name].direct_target == a2b.name
    assert engine._armies[b2f.name].direct_target == a2b.name

    # Column 3: no blue armies -> red units retarget to nearest enemy (column 2 front)
    assert engine._armies[a3f.name].direct_target == b2f.name
    assert engine._armies[a3b.name].direct_target == b2f.name


def test_diagonal_engagement_time():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab()
    pos_a = tab.slot_coords["team1"][0]  # top outer
    pos_b = tab.slot_coords["team2"][1]  # top inner -> diagonal target

    a = make_army("A")
    b = make_army("B")

    layout = {
        "red": [{"army": a, "position": pos_a, "column": 0, "row": 0}],
        "blue": [{"army": b, "position": pos_b, "column": 1, "row": 0}],
    }

    engine = ArenaEngine()
    engine.start_arena_battle(layout)

    from math import hypot

    dist = hypot(pos_b[0] - pos_a[0], pos_b[1] - pos_a[1])
    required_sum = (dist - ENGAGEMENT_DISTANCE) / 1.87
    ctx_a = engine._armies[a.name]
    ctx_b = engine._armies[b.name]
    assert ctx_a.speed + ctx_b.speed == pytest.approx(required_sum)

    elapsed = 0.0
    while True:
        engine.tick(0.05)
        elapsed += 0.05
        ax, ay = engine._armies[a.name].position
        bx, by = engine._armies[b.name].position
        if hypot(ax - bx, ay - by) <= ENGAGEMENT_DISTANCE:
            break
        assert elapsed < 3.0
    assert elapsed == pytest.approx(1.9, abs=0.051)


def test_diagonal_attacker_arrives_with_frontline():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab
    from math import hypot

    tab = ArenaTab()
    pos_diag = tab.slot_coords["team1"][0]
    pos_front = tab.slot_coords["team1"][1]
    pos_enemy = tab.slot_coords["team2"][1]

    diag = make_army("D")
    front = make_army("F")
    enemy = make_army("E")

    layout = {
        "red": [
            {"army": front, "position": pos_front, "column": 1, "row": 0},
            {"army": diag, "position": pos_diag, "column": 0, "row": 0},
        ],
        "blue": [{"army": enemy, "position": pos_enemy, "column": 1, "row": 0}],
    }

    engine = ArenaEngine()
    engine.start_arena_battle(layout)

    elapsed = 0.0
    while True:
        engine.tick(0.05)
        elapsed += 0.05
        dx, dy = engine._armies[diag.name].position
        ex, ey = engine._armies[enemy.name].position
        if hypot(dx - ex, dy - ey) <= ENGAGEMENT_DISTANCE:
            break
        assert elapsed < 3.0
    assert elapsed == pytest.approx(1.95, abs=0.051)


def test_backrow_engagement_time():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab
    from math import hypot

    tab = ArenaTab()
    pos_front = tab.slot_coords["team1"][1]
    pos_back = tab.slot_coords["team1"][5]
    pos_enemy = tab.slot_coords["team2"][1]

    front = make_army("F")
    back = make_army("B")
    enemy = make_army("E")

    layout = {
        "red": [
            {"army": front, "position": pos_front, "column": 1, "row": 0},
            {"army": back, "position": pos_back, "column": 1, "row": 1},
        ],
        "blue": [{"army": enemy, "position": pos_enemy, "column": 1, "row": 0}],
    }

    engine = ArenaEngine()
    engine.start_arena_battle(layout)

    elapsed = 0.0
    while True:
        engine.tick(0.05)
        elapsed += 0.05
        bx, by = engine._armies[back.name].position
        ex, ey = engine._armies[enemy.name].position
        if hypot(bx - ex, by - ey) <= ENGAGEMENT_DISTANCE:
            break
        assert elapsed < 6.0
    assert elapsed == pytest.approx(4.0, abs=0.051)


def test_diagonal_backrow_engagement_time():
    app = _get_app()
    from vr_game_sim.gui_main import ArenaTab
    from math import hypot

    tab = ArenaTab()
    pos_front = tab.slot_coords["team1"][1]
    pos_back = tab.slot_coords["team1"][4]
    pos_enemy = tab.slot_coords["team2"][1]

    front = make_army("F")
    back = make_army("B")
    enemy = make_army("E")

    layout = {
        "red": [
            {"army": front, "position": pos_front, "column": 1, "row": 0},
            {"army": back, "position": pos_back, "column": 0, "row": 1},
        ],
        "blue": [{"army": enemy, "position": pos_enemy, "column": 1, "row": 0}],
    }

    engine = ArenaEngine()
    engine.start_arena_battle(layout)

    elapsed = 0.0
    while True:
        engine.tick(0.05)
        elapsed += 0.05
        bx, by = engine._armies[back.name].position
        ex, ey = engine._armies[enemy.name].position
        if hypot(bx - ex, by - ey) <= ENGAGEMENT_DISTANCE:
            break
        assert elapsed < 6.0
    assert elapsed == pytest.approx(5.1, abs=0.051)


def test_arena_engine_respects_debug_settings(monkeypatch):
    init_kwargs: list[dict[str, object]] = []
    original_init = game_simulator.GameSimulator.__init__

    def tracking_init(
        self,
        army1,
        army2,
        report_builder=None,
        track_stats=True,
        mode="standard",
        cooldowns_enabled=True,
        *,
        hero_cooldowns_enabled=None,
        plugin_cooldowns_enabled=None,
        gem_cooldowns_enabled=None,
        mount_cooldowns_enabled=None,
        damage_reduction_affects_dots=True,
        advantage_mode="multiplicative",
    ):
        init_kwargs.append(
            {
                "cooldowns_enabled": cooldowns_enabled,
                "hero_cooldowns_enabled": hero_cooldowns_enabled,
                "plugin_cooldowns_enabled": plugin_cooldowns_enabled,
                "gem_cooldowns_enabled": gem_cooldowns_enabled,
                "mount_cooldowns_enabled": mount_cooldowns_enabled,
                "damage_reduction_affects_dots": damage_reduction_affects_dots,
                "advantage_mode": advantage_mode,
            }
        )
        return original_init(
            self,
            army1,
            army2,
            report_builder,
            track_stats,
            mode,
            cooldowns_enabled,
            hero_cooldowns_enabled=hero_cooldowns_enabled,
            plugin_cooldowns_enabled=plugin_cooldowns_enabled,
            gem_cooldowns_enabled=gem_cooldowns_enabled,
            mount_cooldowns_enabled=mount_cooldowns_enabled,
            damage_reduction_affects_dots=damage_reduction_affects_dots,
            advantage_mode=advantage_mode,
        )

    monkeypatch.setattr(game_simulator.GameSimulator, "__init__", tracking_init)
    engine = ArenaEngine(
        cooldowns_enabled=False,
        hero_cooldowns_enabled=False,
        plugin_cooldowns_enabled=False,
        damage_reduction_affects_dots=False,
        advantage_mode="off",
    )
    a1 = make_army("A1")
    a2 = make_army("A2")
    layout = {
        "red": [{"army": a1, "position": (0.0, 0.0), "column": 0, "row": 0}],
        "blue": [
            {
                "army": a2,
                "position": (0.0, ENGAGEMENT_DISTANCE - 1.0),
                "column": 0,
                "row": 0,
            }
        ],
    }
    engine.start_arena_battle(layout)
    engine.tick(1.0)

    assert init_kwargs
    kwargs = init_kwargs[0]
    assert kwargs["cooldowns_enabled"] is False
    assert kwargs["hero_cooldowns_enabled"] is False
    assert kwargs["plugin_cooldowns_enabled"] is False
    assert kwargs["damage_reduction_affects_dots"] is False
    assert kwargs["advantage_mode"] == "off"


def test_arena_batch_uses_parent_debug_settings(monkeypatch):
    app = _get_app()
    init_kwargs: list[dict[str, object]] = []
    original_init = game_simulator.GameSimulator.__init__

    def tracking_init(
        self,
        army1,
        army2,
        report_builder=None,
        track_stats=True,
        mode="standard",
        cooldowns_enabled=True,
        *,
        hero_cooldowns_enabled=None,
        plugin_cooldowns_enabled=None,
        gem_cooldowns_enabled=None,
        mount_cooldowns_enabled=None,
        damage_reduction_affects_dots=True,
        advantage_mode="multiplicative",
    ):
        init_kwargs.append(
            {
                "cooldowns_enabled": cooldowns_enabled,
                "plugin_cooldowns_enabled": plugin_cooldowns_enabled,
                "damage_reduction_affects_dots": damage_reduction_affects_dots,
                "advantage_mode": advantage_mode,
            }
        )
        return original_init(
            self,
            army1,
            army2,
            report_builder,
            track_stats,
            mode,
            cooldowns_enabled,
            hero_cooldowns_enabled=hero_cooldowns_enabled,
            plugin_cooldowns_enabled=plugin_cooldowns_enabled,
            gem_cooldowns_enabled=gem_cooldowns_enabled,
            mount_cooldowns_enabled=mount_cooldowns_enabled,
            damage_reduction_affects_dots=damage_reduction_affects_dots,
            advantage_mode=advantage_mode,
        )

    monkeypatch.setattr(game_simulator.GameSimulator, "__init__", tracking_init)

    class DummyWindow(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.hero_cooldowns_enabled = False
            self.plugin_cooldowns_enabled = False
            self.gem_cooldowns_enabled = True
            self.mount_cooldowns_enabled = True
            self.damage_reduction_affects_dots = False
            self.troop_advantage_mode = "additive"

        def update_arena_figures(self, *_: object) -> None:
            pass

    from vr_game_sim.gui_main import ArenaTab

    tab = ArenaTab(DummyWindow())
    cfg_common = {
        "unit_type": "infantry",
        "tier": 5,
        "count": 5,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }
    cfg1 = {"army_name": "Alpha", **cfg_common}
    cfg2 = {"army_name": "Bravo", **cfg_common}
    tab._slot_army[("team1", 0)] = {"config": cfg1, "team": "red", "speed": 50.0}
    tab._slot_army[("team2", 0)] = {"config": cfg2, "team": "blue", "speed": 50.0}

    tab._run_batch(count=1)

    assert init_kwargs
    kwargs = init_kwargs[0]
    assert kwargs["cooldowns_enabled"] is False
    assert kwargs["plugin_cooldowns_enabled"] is False
    assert kwargs["damage_reduction_affects_dots"] is False
    assert kwargs["advantage_mode"] == "additive"
