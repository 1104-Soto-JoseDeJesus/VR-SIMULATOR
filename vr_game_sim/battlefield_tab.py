"""GUI tab for interacting with the multi-army battlefield."""
from __future__ import annotations

from typing import List
import copy
import math
from pathlib import Path

from PyQt6 import QtCore, QtWidgets, QtGui

from .battlefield import Battlefield, step_towards
from .army_composition import Army
from .game_simulator import GameSimulator
from .main import create_armies_from_data


class HexCellItem(QtWidgets.QGraphicsPolygonItem):
    """Single hex tile that can display army icons."""

    def __init__(self, q: int, r: int, size: float):
        self.q = q
        self.r = r
        self.size = size
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            points.append(QtCore.QPointF(size * math.cos(angle), size * math.sin(angle)))
        polygon = QtGui.QPolygonF(points)
        super().__init__(polygon)
        self.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black))
        self.text = QtWidgets.QGraphicsSimpleTextItem("", self)
        self.text.setPos(-size / 2, -size / 3)
        self.main_icon: QtWidgets.QGraphicsPixmapItem | None = None
        self.sec_icon: QtWidgets.QGraphicsPixmapItem | None = None
        bar_y = size * 0.8
        bar_w = size * 1.6
        bar_h = size * 0.2
        self._hp_bg = QtWidgets.QGraphicsRectItem(-bar_w / 2, bar_y, bar_w, bar_h, self)
        self._hp_bg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.black))
        self._hp_bg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        self._hp_bg.setZValue(10)
        self._hp_fg = QtWidgets.QGraphicsRectItem(-bar_w / 2, bar_y, bar_w, bar_h, self)
        self._hp_fg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))
        self._hp_fg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.transparent))
        self._hp_fg.setZValue(11)

    def set_army(self, army: Army | None) -> None:
        if self.main_icon:
            self.scene().removeItem(self.main_icon)
            self.main_icon = None
        if self.sec_icon:
            self.scene().removeItem(self.sec_icon)
            self.sec_icon = None
        if army is None:
            self.text.setText("")
            self._hp_bg.hide()
            self._hp_fg.hide()
            return

        # Display main hero portrait if available.  ``QPixmap.scaled`` expects
        # integer dimensions; passing floats can raise a ``TypeError`` which
        # previously crashed the tab when armies had heroes.  Clamp the image
        # inside the hex cell and convert dimensions to ``int`` for safety.
        if army.heroes:
            hero = army.heroes[0]
            img_path = Path(__file__).resolve().parent / "Hero Images" / f"{hero.name}.png"
            if img_path.exists():
                pix = QtGui.QPixmap(str(img_path))
                pix = pix.scaled(
                    int(self.size * 1.6),  # keep portrait within cell bounds
                    int(self.size * 1.6),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self.main_icon = QtWidgets.QGraphicsPixmapItem(pix, self)
                self.main_icon.setOffset(-pix.width() / 2, -pix.height() / 2)
                self.text.setText("")
            else:
                self.text.setText(army.name[:1].upper())
        else:
            self.text.setText(army.name[:1].upper())

        # Update troop health bar
        self._hp_bg.show()
        self._hp_fg.show()
        ratio = 0.0
        if army.unit.initial_count > 0:
            ratio = max(0.0, min(1.0, army.current_troop_count / army.unit.initial_count))
        rect = self._hp_bg.rect()
        self._hp_fg.setRect(rect.x(), rect.y(), rect.width() * ratio, rect.height())

        # Secondary hero portrait in bottom-right corner
        if army.heroes and len(army.heroes) > 1:
            hero2 = army.heroes[1]
            img2_path = Path(__file__).resolve().parent / "Hero Images" / f"{hero2.name}.png"
            if img2_path.exists():
                pix2 = QtGui.QPixmap(str(img2_path))
                pix2 = pix2.scaled(
                    int(self.size * 0.8),
                    int(self.size * 0.8),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self.sec_icon = QtWidgets.QGraphicsPixmapItem(pix2, self)
                self.sec_icon.setOffset(self.size - pix2.width(), self.size - pix2.height())


class HexBattlefieldView(QtWidgets.QGraphicsView):
    """Graphics view rendering a hexagonal battlefield."""

    armyDropped = QtCore.pyqtSignal(int, int, int)
    armyDoubleClicked = QtCore.pyqtSignal(int)

    def __init__(self, tab: "BattlefieldTab") -> None:
        super().__init__()
        self._tab = tab
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._drag_idx: int | None = None
        self._zoom = 1.0
        self._base_size = 30.0
        self._cells: dict[tuple[int, int], HexCellItem] = {}
        self._build_grid()

    def _build_grid(self) -> None:
        size = self._base_size
        for r in range(self._tab.battlefield.height):
            for q in range(self._tab.battlefield.width):
                cell = HexCellItem(q, r, size)
                x = size * math.sqrt(3) * (q + (r % 2) / 2)
                y = size * 1.5 * r
                cell.setPos(x, y)
                self._scene.addItem(cell)
                self._cells[(q, r)] = cell
        self.setSceneRect(self._scene.itemsBoundingRect())

    def clear_marks(self) -> None:
        for cell in self._cells.values():
            cell.set_army(None)

    def set_army_mark(self, army: Army) -> None:
        cell = self._cells.get((army.x, army.y))
        if cell:
            cell.set_army(army)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, HexCellItem):
                army = self._tab._army_at(item.q, item.r)
                if army:
                    self._drag_idx = self._tab.armies.index(army)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_idx is not None:
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, HexCellItem):
                self.armyDropped.emit(self._drag_idx, item.q, item.r)
            self._drag_idx = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, HexCellItem):
            army = self._tab._army_at(item.q, item.r)
            if army:
                idx = self._tab.armies.index(army)
                self.armyDoubleClicked.emit(idx)
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # type: ignore[override]
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.2, min(self._zoom, 5.0))
        self.resetTransform()
        self.scale(self._zoom, self._zoom)


class BattlefieldTab(QtWidgets.QWidget):
    """Widget to display and control a battlefield."""

    def __init__(self, main_window: 'MainWindow', width: int = 16, height: int = 16) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self.battlefield = Battlefield(width, height)
        self.armies: List[Army] = []
        self.army_configs: List[dict] = []

        layout = QtWidgets.QVBoxLayout(self)

        # Grid representing the battlefield
        self.grid = HexBattlefieldView(self)
        self.grid.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.grid.armyDropped.connect(self._drag_move)
        self.grid.armyDoubleClicked.connect(self._edit_army)
        layout.addWidget(self.grid, 1)

        reset_btn = QtWidgets.QPushButton("Reset from Setup")
        reset_btn.clicked.connect(self._reset_from_setup)
        layout.addWidget(reset_btn)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        self._reset_from_setup()

    # ------------------------------------------------------------------
    def _reset_from_setup(self) -> None:
        """Rebuild armies from the main window's setup data."""
        setup_data = [
            copy.deepcopy(self._main_window.army1_frame.build_config()),
            copy.deepcopy(self._main_window.army2_frame.build_config()),
        ]
        self.army_configs = setup_data
        self.armies = create_armies_from_data(self.army_configs)
        if not self.armies:
            return
        # Place first two armies at opposite corners
        self.battlefield.place_army(self.armies[0], 0, 0)
        if len(self.armies) > 1:
            self.battlefield.place_army(
                self.armies[1], self.battlefield.width - 1, self.battlefield.height - 1
            )
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        self.grid.clear_marks()
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            if self.battlefield.within_bounds(army.x, army.y):
                self.grid.set_army_mark(army)

    # ------------------------------------------------------------------
    def _army_at(self, x: int, y: int) -> Army | None:
        for army in self.armies:
            if army.current_troop_count > 0 and army.x == x and army.y == y:
                return army
        return None

    def _drag_move(self, idx: int, x: int, y: int) -> None:
        if 0 <= idx < len(self.armies):
            if self.battlefield.within_bounds(x, y):
                self.armies[idx].set_destination((x, y))

    def _edit_army(self, idx: int) -> None:
        if not (0 <= idx < len(self.armies)):
            return
        dialog = ArmyConfigDialog(self.army_configs[idx], self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dialog.build_config()
            self.army_configs[idx] = cfg
            x, y = self.armies[idx].x, self.armies[idx].y
            self.armies[idx] = create_armies_from_data([cfg])[0]
            self.battlefield.place_army(self.armies[idx], x, y)
            self._refresh_grid()

    def _check_conflicts(self) -> None:
        positions: dict[tuple[int, int], list[Army]] = {}
        for army in self.armies:
            if army.current_troop_count <= 0 or army.battle_time_remaining > 0:
                continue
            positions.setdefault((army.x, army.y), []).append(army)
        for armies_here in positions.values():
            while len(armies_here) > 1:
                a1 = armies_here.pop(0)
                a2 = armies_here.pop(0)
                self._resolve_battle(a1, a2)
                if a1.current_troop_count > 0 and a1.battle_time_remaining == 0:
                    armies_here.insert(0, a1)
                if a2.current_troop_count > 0 and a2.battle_time_remaining == 0:
                    armies_here.insert(0, a2)
        self.armies = [a for a in self.armies if a.current_troop_count > 0]

    def _tick(self) -> None:
        for army in self.armies:
            army.progress_battle()
        self.armies = [a for a in self.armies if a.current_troop_count > 0]

        dest_map: dict[tuple[int, int], list[Army]] = {}
        for army in self.armies:
            if (
                army.current_troop_count > 0
                and army.battle_time_remaining == 0
                and army.destination is not None
            ):
                dest_map.setdefault(army.destination, []).append(army)
        for armies_dest in dest_map.values():
            while len(armies_dest) > 1:
                a1 = armies_dest.pop(0)
                a2 = armies_dest.pop(0)
                self._resolve_battle(a1, a2)
                if a1.current_troop_count > 0 and a1.battle_time_remaining == 0:
                    armies_dest.insert(0, a1)
                if a2.current_troop_count > 0 and a2.battle_time_remaining == 0:
                    armies_dest.insert(0, a2)

        for army in self.armies:
            if army.current_troop_count > 0 and army.battle_time_remaining == 0:
                if army.destination:
                    step = step_towards(self.battlefield, (army.x, army.y), army.destination)
                    occupant = self._army_at(*step)
                    if occupant and occupant is not army:
                        if occupant.battle_time_remaining == 0:
                            self._resolve_battle(army, occupant)
                        continue
                army.update_position(self.battlefield)

        self._check_conflicts()
        self._refresh_grid()

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        sim_a = copy.deepcopy(army1)
        sim_b = copy.deepcopy(army2)
        sim_a.unit.initial_count = int(army1.current_troop_count)
        sim_b.unit.initial_count = int(army2.current_troop_count)
        simulator = GameSimulator(sim_a, sim_b, track_stats=False)
        simulator.simulate_battle()
        duration = simulator.round
        army1.engage(sim_a.current_troop_count, sim_a.unrevivable_troops, duration)
        army2.engage(sim_b.current_troop_count, sim_b.unrevivable_troops, duration)


class ArmyConfigDialog(QtWidgets.QDialog):
    """Popup dialog for configuring an individual battlefield army."""

    def __init__(self, cfg: dict | None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        from .gui_main import ArmyFrame  # Imported here to avoid circular import

        self.setWindowTitle("Army Configuration")
        layout = QtWidgets.QVBoxLayout(self)
        self.frame = ArmyFrame(1, self)
        if cfg:
            self.frame.populate_from_config(cfg)
        layout.addWidget(self.frame)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_config(self) -> dict:
        return self.frame.build_config()
