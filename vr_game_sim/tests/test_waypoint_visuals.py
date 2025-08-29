import os

from PyQt6 import QtWidgets

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def _get_app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_speed_spin_allows_high_values():
    app = _get_app()
    from vr_game_sim.gui_main import ArmySetupDialog

    dlg = ArmySetupDialog()
    assert dlg.speed_spin.maximum() == 100.0


def test_path_visuals_drawn_for_waypoints():
    app = _get_app()
    from vr_game_sim.gui_main import BattlefieldTab

    tab = BattlefieldTab()
    tab._timer.stop()

    unit = Unit("pikemen", 5, initial_count=10)
    army = Army("A", unit)
    tab.engine.add_army(army, "red", position=(0.0, 0.0), speed=1.0)
    path = [(10.0, 0.0), (20.0, 0.0)]
    tab.engine.set_path("A", path)
    ctx = tab.engine._armies["A"]
    tab._update_path_visual("A", ctx.position, ctx.path)

    items = tab._paths.get("A")
    assert items is not None

    from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem

    # One line per segment plus a circle marker at the end
    assert len(items) == len(path) + 1
    assert isinstance(items[-1], QGraphicsEllipseItem)
    for itm in items[:-1]:
        assert isinstance(itm, QGraphicsLineItem)
