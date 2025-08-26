"""GUI tab for interacting with the multi-army battlefield."""
from __future__ import annotations

from typing import List
import copy
import math
import json
from pathlib import Path

from PyQt6 import QtCore, QtWidgets, QtGui

from .battlefield import Battlefield
from .army_composition import Army
from .main import create_armies_from_data
from .multi_army_simulator import MultiArmySimulator
from .navmesh import NavMesh, Polygon
from .constants import ENGAGEMENT_RADIUS


SAVED_ARMIES_FILE = Path(__file__).resolve().parent / "setups" / "saved_armies.json"


def load_saved_armies() -> dict[str, dict]:
    """Return dictionary of saved army configs keyed by name."""
    if SAVED_ARMIES_FILE.exists():
        try:
            with open(SAVED_ARMIES_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_army_config(name: str, cfg: dict) -> None:
    """Persist a single army configuration under ``name``."""
    data = load_saved_armies()
    data[name] = cfg
    SAVED_ARMIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SAVED_ARMIES_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4)
class ArmyItem(QtWidgets.QGraphicsItem):
    """Movable graphics item representing an army at float coordinates."""

    def __init__(self, army: Army, size: float):
        super().__init__()
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, True)
        self.army = army
        self.size = size
        self.text = QtWidgets.QGraphicsSimpleTextItem("", self)
        self.text.setPos(-size / 2, -size / 3)
        self.text.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.main_icon: QtWidgets.QGraphicsPixmapItem | None = None
        self.sec_icon: QtWidgets.QGraphicsPixmapItem | None = None
        bar_h = size * 1.6
        bar_w = size * 0.2
        bar_x = -size * 0.9
        bar_y = -bar_h / 2
        self._hp_bg = QtWidgets.QGraphicsRectItem(bar_x, bar_y, bar_w, bar_h, self)
        self._hp_bg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.black))
        self._hp_bg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        self._hp_bg.setZValue(10)
        self._hp_bg.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._hp_fg = QtWidgets.QGraphicsRectItem(bar_x, bar_y, bar_w, bar_h, self)
        self._hp_fg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))
        self._hp_fg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.transparent))
        self._hp_fg.setZValue(11)
        self._hp_fg.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._highlight = QtWidgets.QGraphicsRectItem(-size, -size, 2 * size, 2 * size, self)
        highlight_pen = QtGui.QPen(QtCore.Qt.GlobalColor.yellow)
        highlight_pen.setWidth(3)
        self._highlight.setPen(highlight_pen)
        self._highlight.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.transparent))
        self._highlight.setZValue(12)
        self._highlight.setVisible(False)
        self._highlight.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.update_from_army(army)

    def update_from_army(self, army: Army) -> None:
        self.army = army
        if self.main_icon:
            self.scene().removeItem(self.main_icon)
            self.main_icon = None
        if self.sec_icon:
            self.scene().removeItem(self.sec_icon)
            self.sec_icon = None

        if army.heroes:
            hero = army.heroes[0]
            img_path = Path(__file__).resolve().parent / "Hero Images" / f"{hero.name}.png"
            if img_path.exists():
                pix = QtGui.QPixmap(str(img_path))
                pix = pix.scaled(
                    int(self.size * 1.6),
                    int(self.size * 1.6),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self.main_icon = QtWidgets.QGraphicsPixmapItem(pix, self)
                self.main_icon.setOffset(-pix.width() / 2, -pix.height() / 2)
                self.main_icon.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
                self.text.setText("")
            else:
                self.text.setText(army.name[:1].upper())
        else:
            self.text.setText(army.name[:1].upper())

        self._hp_bg.show()
        self._hp_fg.show()
        ratio = 0.0
        if army.unit.initial_count > 0:
            ratio = max(0.0, min(1.0, army.current_troop_count / army.unit.initial_count))
        rect = self._hp_bg.rect()
        self._hp_fg.setRect(
            rect.x(), rect.y() + rect.height() * (1 - ratio), rect.width(), rect.height() * ratio
        )

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
                self.sec_icon.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlight.setVisible(highlighted)

    # ``QGraphicsItem`` is abstract and requires ``boundingRect`` even when we
    # delegate all rendering to child items.  Provide a small rectangle that
    # comfortably encloses the portrait and health bar so Qt can perform
    # hit-tests and updates without error.
    def boundingRect(self) -> QtCore.QRectF:  # type: ignore[override]
        s = self.size
        return QtCore.QRectF(-s, -s, 2 * s, 2 * s)


class BattlefieldView(QtWidgets.QGraphicsView):
    """Graphics view rendering a plain battlefield without hex overlay."""

    armyDropped = QtCore.pyqtSignal(int, float, float)
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
        self._hover_target: ArmyItem | None = None
        self._zoom = 1.0
        self._base_size = 30.0
        self._build_grid()
        self.army_items: List[ArmyItem] = []
        self.setMouseTracking(True)

    def _build_grid(self) -> None:
        size = self._base_size
        rect = QtCore.QRectF(0, 0, size * self._tab.battlefield.width, size * self._tab.battlefield.height)
        self._scene.setSceneRect(rect)
        bg_path = Path(__file__).resolve().parent / "Icons" / "BattlefieldBackground.png"
        if bg_path.exists():
            pix = QtGui.QPixmap(str(bg_path))
            pix = pix.scaled(
                int(rect.width()),
                int(rect.height()),
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            bg_item = QtWidgets.QGraphicsPixmapItem(pix)
            bg_item.setZValue(-100)
            self._scene.addItem(bg_item)

    def add_army_item(self, item: ArmyItem) -> None:
        self._scene.addItem(item)
        self.army_items.append(item)

    def remove_army_item(self, item: ArmyItem) -> None:
        if item in self.army_items:
            self.army_items.remove(item)
        self._scene.removeItem(item)
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            x, y = self._scene_to_coords(scene_pt)
            army = self._tab._army_at(x, y)
            if army:
                self._drag_idx = self._tab.armies.index(army)
                if self._hover_target:
                    self._hover_target.set_highlighted(False)
                    self._hover_target = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_idx is not None:
            scene_pt = self.mapToScene(event.position().toPoint())
            x, y = self._scene_to_coords(scene_pt)
            army = self._tab._army_at(x, y)
            new_target: ArmyItem | None = None
            if army and army.team != self._tab.armies[self._drag_idx].team:
                try:
                    idx = self._tab.armies.index(army)
                    new_target = self.army_items[idx]
                except ValueError:
                    new_target = None
            if self._hover_target is not new_target:
                if self._hover_target:
                    self._hover_target.set_highlighted(False)
                self._hover_target = new_target
                if self._hover_target:
                    self._hover_target.set_highlighted(True)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_idx is not None:
            scene_pt = self.mapToScene(event.position().toPoint())
            x, y = self._scene_to_coords(scene_pt)
            if self._hover_target:
                target_army = self._hover_target.army
                self.armyDropped.emit(self._drag_idx, target_army.float_x, target_army.float_y)
                self._hover_target.set_highlighted(False)
                self._hover_target = None
            elif self._tab.battlefield.within_bounds(x, y):
                self.armyDropped.emit(self._drag_idx, x, y)
            self._drag_idx = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        scene_pt = self.mapToScene(event.position().toPoint())
        x, y = self._scene_to_coords(scene_pt)
        army = self._tab._army_at(x, y)
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

    # ------------------------------------------------------------------
    def _scene_to_coords(self, pt: QtCore.QPointF) -> tuple[float, float]:
        """Convert scene coordinates to battlefield float coordinates."""
        size = self._base_size
        return pt.x() / size, pt.y() / size


class BattlefieldTab(QtWidgets.QWidget):
    """Widget to display and control a battlefield."""

    reportsUpdated = QtCore.pyqtSignal()

    def __init__(self, main_window: 'MainWindow', width: int = 16, height: int = 16) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self.battlefield = Battlefield(width, height)
        self.armies: List[Army] = []
        self.army_configs: List[dict] = []
        self.sim: MultiArmySimulator | None = None

        layout = QtWidgets.QVBoxLayout(self)

        # Grid representing the battlefield
        self.grid = BattlefieldView(self)
        self.army_items = self.grid.army_items
        self.grid.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.grid.armyDropped.connect(self._drag_move)
        self.grid.armyDoubleClicked.connect(self._edit_army)
        layout.addWidget(self.grid, 1)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add Army")
        add_btn.clicked.connect(self._add_army)
        btn_row.addWidget(add_btn)
        reset_btn = QtWidgets.QPushButton("Reset from Setup")
        reset_btn.clicked.connect(self._reset_from_setup)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        # Update one hundred times per second for smoother movement
        self._timer.start(10)

        # Start with an empty battlefield; armies must be added manually
        self.sim = MultiArmySimulator(self.battlefield, self.armies)
        w, h = self.battlefield.width, self.battlefield.height
        poly = Polygon(vertices=[(-1, -1), (w, -1), (w, h), (-1, h)], neighbors=[])
        self.battlefield.load_navmesh(NavMesh([poly]))
        self._refresh_grid()

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
        for item in list(self.army_items):
            self.grid.remove_army_item(item)
        # Do not replace ``army_items`` with a new list; keep sharing the view's list
        # to avoid duplicating graphics items on refresh.
        self.army_items.clear()
        # Assign teams and place first two armies at opposite corners
        self.armies[0].team = 0
        self.battlefield.place_army(self.armies[0], 0, 0)
        item0 = ArmyItem(self.armies[0], self.grid._base_size)
        self.grid.add_army_item(item0)
        if len(self.armies) > 1:
            self.armies[1].team = 1
            # Spawn slightly inside the far corner to ensure visibility within bounds
            x = max(0, self.battlefield.width - 2)
            y = max(0, self.battlefield.height - 2)
            self.battlefield.place_army(self.armies[1], x, y)
            item1 = ArmyItem(self.armies[1], self.grid._base_size)
            self.grid.add_army_item(item1)
        # Load a simple navmesh covering the entire battlefield for straight paths
        w, h = self.battlefield.width, self.battlefield.height
        poly = Polygon(vertices=[(-1, -1), (w, -1), (w, h), (-1, h)], neighbors=[])
        self.battlefield.load_navmesh(NavMesh([poly]))
        self.sim = MultiArmySimulator(self.battlefield, self.armies)
        self._refresh_grid()
        self.reportsUpdated.emit()

    def _refresh_grid(self) -> None:
        # Remove items for armies no longer present
        for item in list(self.army_items):
            if item.army not in self.armies or item.army.current_troop_count <= 0:
                self.grid.remove_army_item(item)
        # Ensure every army has an item and update positions
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            item = next((it for it in self.army_items if it.army is army), None)
            if not item:
                item = ArmyItem(army, self.grid._base_size)
                self.grid.add_army_item(item)
            else:
                item.update_from_army(army)
            size = self.grid._base_size
            x = size * army.float_x
            y = size * army.float_y
            item.setPos(x, y)

    # ------------------------------------------------------------------
    def _clear_targeting(self, army: Army) -> None:
        if army.direct_target and army in army.direct_target.attackers:
            army.direct_target.attackers.remove(army)
        for atk in list(army.attackers):
            atk.direct_target = None
        army.direct_target = None
        army.attackers.clear()

    def _set_targeting(self, attacker: Army, defender: Army) -> None:
        """Assign ``attacker`` to engage ``defender``.

        This mirrors the targeting rules in :class:`MultiArmySimulator` but is
        used here when the user drags an army onto an enemy tile.  The first
        attacker to claim a defender becomes that defender's direct target,
        enabling full attacks, while subsequent attackers are recorded only in
        ``defender.attackers`` so they can counter but not initiate basic
        attacks.
        """

        if attacker.team == defender.team or attacker.direct_target is defender:
            return
        self._clear_targeting(attacker)
        attacker.direct_target = defender
        if attacker not in defender.attackers:
            defender.attackers.append(attacker)
        if defender.direct_target is None:
            defender.direct_target = attacker

    # ------------------------------------------------------------------
    def _army_at(self, x: float, y: float) -> Army | None:
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            if math.hypot(army.float_x - x, army.float_y - y) <= ENGAGEMENT_RADIUS:
                return army
        return None

    def _drag_move(self, idx: int, x: float, y: float) -> None:
        if 0 <= idx < len(self.armies) and self.battlefield.within_bounds(x, y):
            army = self.armies[idx]
            army.set_destination((x, y))
            occupant = self._army_at(x, y)
            if not occupant or occupant.team == army.team:
                self._clear_targeting(army)
            else:
                self._set_targeting(army, occupant)

    def _edit_army(self, idx: int) -> None:
        if not (0 <= idx < len(self.armies)):
            return
        dialog = ArmyConfigDialog(self.army_configs[idx], self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dialog.build_config()
            self.army_configs[idx] = cfg
            old_army = self.armies[idx]
            self._clear_targeting(old_army)
            x, y = old_army.x, old_army.y
            team = old_army.team
            reports = old_army.battle_reports
            new_army = create_armies_from_data([cfg])[0]
            new_army.team = team
            new_army.battle_reports = reports
            self.armies[idx] = new_army
            self.battlefield.place_army(new_army, x, y)
            if self.sim:
                self.sim.armies[idx] = new_army
            if 0 <= idx < len(self.army_items):
                self.army_items[idx].update_from_army(new_army)
            self._refresh_grid()
            self.reportsUpdated.emit()

    def _tick(self) -> None:
        if self.sim:
            self.sim.step(0.01)
            self.reportsUpdated.emit()
        self._refresh_grid()

    # ------------------------------------------------------------------
    def _add_army(self) -> None:
        """Add a new army to the battlefield up to team limits."""
        saved = load_saved_armies()
        cfg: dict
        if saved:
            names = ["<New>"] + sorted(saved.keys())
            name, ok = QtWidgets.QInputDialog.getItem(
                self, "Add Army", "Select saved army or create new:", names, 0, False
            )
            if not ok:
                return
            if name != "<New>":
                cfg = copy.deepcopy(saved[name])
            else:
                dialog = ArmyConfigDialog(None, self)
                if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    return
                cfg = dialog.build_config()
        else:
            dialog = ArmyConfigDialog(None, self)
            if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
            cfg = dialog.build_config()
        team, ok = QtWidgets.QInputDialog.getInt(self, "Select Team", "Team (1 or 2):", 1, 1, 2)
        if not ok:
            return
        team_idx = team - 1
        if sum(1 for a in self.armies if a.team == team_idx) >= 5:
            QtWidgets.QMessageBox.warning(self, "Team Full", "Each team may have at most 5 armies.")
            return
        army = create_armies_from_data([cfg])[0]
        army.team = team_idx
        self.army_configs.append(cfg)
        # Find spawn
        spawn = self._find_spawn(team_idx)
        if spawn:
            self.battlefield.place_army(army, *spawn)
        else:
            self.battlefield.place_army(army, 0, 0)
        self.armies.append(army)
        item = ArmyItem(army, self.grid._base_size)
        self.grid.add_army_item(item)
        if self.sim and army not in self.sim.armies:
            self.sim.armies.append(army)
        self._refresh_grid()
        self.reportsUpdated.emit()

    def _find_spawn(self, team: int) -> tuple[int, int] | None:
        if team == 0:
            for r in range(self.battlefield.height):
                for q in range(self.battlefield.width):
                    if not self._army_at(q, r):
                        return q, r
        else:
            for r in reversed(range(max(1, self.battlefield.height - 1))):
                for q in reversed(range(max(1, self.battlefield.width - 1))):
                    if not self._army_at(q, r):
                        return q, r
        return None


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
        save_btn = buttons.addButton("Save", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        save_btn.clicked.connect(self._save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_config(self) -> dict:
        return self.frame.build_config()

    def _save(self) -> None:
        cfg = self.build_config()
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Army", "Name:")
        if ok and name:
            save_army_config(name, cfg)
