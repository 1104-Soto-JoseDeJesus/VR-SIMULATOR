from __future__ import annotations

"""Widget for configuring and displaying real-time armies on a map.

This module expands the previous placeholder widget so armies can be created
using the existing 1v1 army setup dialog and placed on the map with their hero
portraits.  Armies are persisted to a JSON file for quick reloading and each
army item shows a vertical health bar representing remaining troops.
"""

from pathlib import Path
import json
import math
from typing import List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets

from .navmesh import NavMesh


class ArmyGraphicsItem(QtWidgets.QGraphicsItemGroup):
    """Composite graphics item displaying hero portraits and a health bar.

    The item handles mouse interaction so that the owning
    :class:`RealTimeBattleWidget` can react when the user releases the item in
    a new location.
    """

    def __init__(
        self,
        main_pixmap: QtGui.QPixmap,
        secondary_pixmap: Optional[QtGui.QPixmap],
        team_color: QtGui.QColor,
        max_troops: int,
        controller: "RealTimeBattleWidget",
    ) -> None:
        super().__init__()

        self._controller = controller

        self.main_item = QtWidgets.QGraphicsPixmapItem(main_pixmap)
        self.addToGroup(self.main_item)

        width = main_pixmap.width()
        height = main_pixmap.height()

        border = QtWidgets.QGraphicsRectItem(0, 0, width, height)
        border.setPen(QtGui.QPen(team_color, 2))
        border.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        self.addToGroup(border)

        if secondary_pixmap is not None:
            scaled = secondary_pixmap.scaled(
                int(width * 0.4),
                int(height * 0.4),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.secondary_item = QtWidgets.QGraphicsPixmapItem(scaled)
            self.secondary_item.setPos(width - scaled.width(), height - scaled.height())
            self.addToGroup(self.secondary_item)
        else:
            self.secondary_item = None

        self.health_bg = QtWidgets.QGraphicsRectItem(-6, 0, 4, height)
        self.health_bg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.darkGray))
        self.health_bg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black))
        self.addToGroup(self.health_bg)

        self.health_fg = QtWidgets.QGraphicsRectItem(-6, 0, 4, height)
        self.health_fg.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.green))
        self.health_fg.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.transparent))
        self.addToGroup(self.health_fg)

        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)

        self.max_troops = max(1, max_troops)
        self.current_troops = max_troops
        self._update_bar()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        """Notify the controller that the item was released.

        The underlying ``ItemIsMovable`` flag already moves the item while the
        user drags it.  On release we simply forward the event so that the
        ``RealTimeBattleWidget`` can commit the destination and potentially
        create attack orders.
        """

        super().mouseReleaseEvent(event)
        # Inform the controller that this item has been dropped.
        if self._controller is not None:
            self._controller.handle_army_drop(self)

    def _update_bar(self) -> None:
        """Update the health bar to reflect current troop count."""
        height = self.main_item.pixmap().height()
        ratio = self.current_troops / self.max_troops if self.max_troops else 0.0
        self.health_fg.setRect(-6, height * (1 - ratio), 4, height * ratio)

    def set_troop_count(self, count: int) -> None:
        self.current_troops = max(0, min(count, self.max_troops))
        self._update_bar()


class ArmyDialog(QtWidgets.QDialog):
    """Dialog embedding the existing ArmyFrame for army creation."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        from .gui_main import ArmyFrame  # Local import to avoid circular import

        self.setWindowTitle("Add Army")
        layout = QtWidgets.QVBoxLayout(self)

        self.army_frame = ArmyFrame(1)
        layout.addWidget(self.army_frame)

        team_layout = QtWidgets.QHBoxLayout()
        team_layout.addWidget(QtWidgets.QLabel("Team:"))
        self.team_combo = QtWidgets.QComboBox()
        self.team_combo.addItems(["1", "2"])
        team_layout.addWidget(self.team_combo)
        layout.addLayout(team_layout)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result(self) -> Tuple[dict, int]:
        return self.army_frame.build_config(), int(self.team_combo.currentText())


class RealTimeBattleWidget(QtWidgets.QWidget):
    """Container widget for the real-time battle view."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        army_file: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)

        self.army_file = Path(army_file) if army_file else Path(__file__).with_name(
            "realtime_armies.json"
        )

        layout = QtWidgets.QVBoxLayout(self)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.map_canvas = QtWidgets.QGraphicsView(self.scene)
        layout.addWidget(self.map_canvas, 1)

        controls_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(controls_layout)

        self.add_button = QtWidgets.QPushButton("Add Army")
        self.save_button = QtWidgets.QPushButton("Save Army")
        self.refresh_button = QtWidgets.QPushButton("Refresh Battlefield")
        controls_layout.addWidget(self.add_button)
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.refresh_button)

        self.add_button.clicked.connect(self.add_army)
        self.save_button.clicked.connect(self._save_armies)
        self.refresh_button.clicked.connect(self._refresh_battlefield)

        nav_path = Path(__file__).with_name("navmesh_sample.json")
        self.navmesh = NavMesh.from_json(nav_path)
        for poly in self.navmesh.polygons.values():
            polygon = QtGui.QPolygonF(
                [QtCore.QPointF(x, y) for x, y in poly.vertices]
            )
            item = QtWidgets.QGraphicsPolygonItem(polygon)
            item.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.lightGray))
            item.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black))
            self.scene.addItem(item)

        self.armies: List[dict] = []
        # Radius within which dropping an army near an enemy will create an
        # attack order.  The value is in scene units and can be tweaked by
        # tests or callers.
        self.attack_radius: float = 30.0

        # ------------------------------------------------------------------
        # Real-time battle state
        # ------------------------------------------------------------------
        # ``current_second`` represents a global timer shared by every army on
        # the battlefield.  When new armies join mid-fight they must wait until
        # the next whole second before taking their first action.  The timer is
        # advanced via :meth:`advance_time` and is intentionally decoupled from
        # Qt's event loop so that tests can manipulate it deterministically.
        self.current_second: int = 0

        self._load_armies()

    def _load_hero_pixmap(self, name: Optional[str]) -> Optional[QtGui.QPixmap]:
        if not name:
            return None
        img_path = Path(__file__).with_name("Hero Images") / f"{name}.png"
        if not img_path.exists():
            return None
        pix = QtGui.QPixmap(str(img_path))
        return pix.scaled(
            64,
            92,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )

    def _add_army_from_config(
        self, cfg: dict, team: int, pos: Optional[QtCore.QPointF] = None
    ) -> None:
        heroes = cfg.get("heroes", [])
        main_name = heroes[0]["hero_name_or_preset"] if heroes else None
        secondary_name = heroes[1]["hero_name_or_preset"] if len(heroes) > 1 else None

        main_pix = self._load_hero_pixmap(main_name)
        if main_pix is None:
            return
        secondary_pix = self._load_hero_pixmap(secondary_name)

        team_color = (
            QtCore.Qt.GlobalColor.red if team == 1 else QtCore.Qt.GlobalColor.blue
        )
        item = ArmyGraphicsItem(
            main_pix,
            secondary_pix,
            QtGui.QColor(team_color),
            cfg.get("count", 0),
            self,
        )
        if pos is not None:
            item.setPos(pos)
        self.scene.addItem(item)
        # Each army keeps track of its current destination and attack target.
        # In addition, a number of attributes are maintained so that tests can
        # simulate real-time combat at a per-second granularity.
        self.armies.append(
            {
                "config": cfg,
                "team": team,
                "item": item,
                "destination": item.pos(),
                "target": None,
                # -- Real-time combat state ---------------------------------
                # ``current_troops`` mirrors the graphics item's troop count.
                "current_troops": cfg.get("count", 0),
                # Next whole second this army may act.  Armies added during an
                # ongoing battle must wait until ``current_second + 1``.
                "next_action_second": self.current_second + 1,
                # Internal round number used by skills that depend on the
                # army's own round counter.
                "own_round": 0,
                # Rage is accumulated once per round based on aggregated
                # attacker inputs.
                "rage": 0.0,
                # Aggregated changes from all attackers during the current
                # second.  These are committed when ``advance_time`` ticks.
                "pending_damage": 0.0,
                "pending_heal": 0.0,
                "pending_rage": 0.0,
                "pending_effects": [],
                # Second when this army last acted. Used for idle detection.
                "last_action_second": self.current_second,
            }
        )

    def add_army(self) -> None:
        dialog = ArmyDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg, team = dialog.result()
            self._add_army_from_config(cfg, team)

    def _save_armies(self) -> None:
        data = []
        for entry in self.armies:
            item = entry["item"]
            pos = item.pos()
            data.append(
                {
                    "config": entry["config"],
                    "team": entry["team"],
                    "pos": [pos.x(), pos.y()],
                }
            )
        try:
            with open(self.army_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError:
            pass

    def _load_armies(self) -> None:
        if not self.army_file.exists():
            return
        try:
            data = json.load(open(self.army_file, "r", encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in data:
            cfg = entry.get("config", {})
            team = int(entry.get("team", 1))
            pos_vals = entry.get("pos", [0, 0])
            pos = QtCore.QPointF(float(pos_vals[0]), float(pos_vals[1]))
            self._add_army_from_config(cfg, team, pos)

    # ------------------------------------------------------------------
    # Interaction logic
    # ------------------------------------------------------------------
    def handle_army_drop(self, item: ArmyGraphicsItem) -> None:
        """Commit an army's new destination and resolve attack orders."""

        entry = next((e for e in self.armies if e["item"] is item), None)
        if entry is None:
            return

        pos = item.pos()
        entry["destination"] = pos

        nearest = None
        nearest_dist = self.attack_radius
        for other in self.armies:
            if other is entry or other["team"] == entry["team"]:
                continue
            other_pos = other["item"].pos()
            dx = pos.x() - other_pos.x()
            dy = pos.y() - other_pos.y()
            dist = math.hypot(dx, dy)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = other

        if nearest is None:
            entry["target"] = None
            return

        enemy_pos = nearest["item"].pos()
        dx = pos.x() - enemy_pos.x()
        dy = pos.y() - enemy_pos.y()
        dist = math.hypot(dx, dy) or 1.0
        snap_x = enemy_pos.x() + dx / dist * 2
        snap_y = enemy_pos.y() + dy / dist * 2
        new_pos = QtCore.QPointF(snap_x, snap_y)
        item.setPos(new_pos)
        entry["destination"] = new_pos

        entry["target"] = nearest
        if nearest.get("target") is None:
            nearest["target"] = entry

    def _refresh_battlefield(self) -> None:
        for entry in self.armies:
            self.scene.removeItem(entry["item"])
        self.armies.clear()

    # ------------------------------------------------------------------
    # Real-time combat helpers
    # ------------------------------------------------------------------
    def queue_damage(
        self,
        attacker_index: int,
        defender_index: int,
        damage: float,
        heal: float = 0.0,
        rage: float = 0.0,
        effects: Optional[List[str]] = None,
    ) -> bool:
        """Aggregate combat input for a defender for the current second.

        Parameters
        ----------
        attacker_index:
            Index of the attacking army in ``self.armies``.
        defender_index:
            Index of the defending army in ``self.armies``.
        damage / heal / rage:
            Values contributed by the attacker for this second.  They are
            aggregated on the defender and committed when ``advance_time`` is
            called.
        effects:
            Optional collection of effect names to apply to the defender.

        Returns
        -------
        bool
            ``True`` if the attacker was allowed to act, ``False`` otherwise.
        """

        if attacker_index >= len(self.armies) or defender_index >= len(self.armies):
            return False
        attacker = self.armies[attacker_index]
        defender = self.armies[defender_index]

        # Enforce the "wait until next whole second" rule.
        if self.current_second < attacker.get("next_action_second", 0):
            return False

        defender["pending_damage"] += float(damage)
        defender["pending_heal"] += float(heal)
        defender["pending_rage"] += float(rage)
        if effects:
            defender["pending_effects"].extend(effects)

        attacker["last_action_second"] = self.current_second
        attacker["own_round"] += 1
        attacker["next_action_second"] = self.current_second + 1
        return True

    def advance_time(self, seconds: int = 1) -> None:
        """Advance the global timer and resolve aggregated actions.

        This processes any pending damage/healing/effects once per round for
        each army and also resets rage and round counters for armies that have
        been idle for at least two seconds.
        """

        for _ in range(max(0, int(seconds))):
            self.current_second += 1
            for entry in self.armies:
                # Commit aggregated combat inputs
                net_hp = entry["pending_heal"] - entry["pending_damage"]
                if net_hp != 0:
                    entry["current_troops"] = max(0.0, entry["current_troops"] + net_hp)
                    entry["item"].set_troop_count(int(entry["current_troops"]))
                entry["rage"] += entry["pending_rage"]

                # Clear pending values for next round
                entry["pending_damage"] = 0.0
                entry["pending_heal"] = 0.0
                entry["pending_rage"] = 0.0
                entry["pending_effects"] = []

                # Handle idle armies: reset rage and own round if idle >=2 seconds
                if self.current_second - entry["last_action_second"] >= 2:
                    entry["rage"] = 0.0
                    entry["own_round"] = 0

