from __future__ import annotations

"""Widget placeholder for real-time battle visualisation.

This widget provides a basic layout containing a map canvas, placeholder
area for army controls and a refresh button.  It is designed to be used as a
stand-alone tab within the main GUI so that loading it does not affect the
existing 1v1 figures tab.  The widget now loads a simple navmesh and moves
an army token along paths constrained to it."""

from pathlib import Path
from typing import List

from PyQt6 import QtCore, QtGui, QtWidgets

from .navmesh import NavMesh


class ArmyItem(QtWidgets.QGraphicsEllipseItem):
    """Draggable item representing an army."""

    def __init__(self, radius: float, drop_callback) -> None:
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.drop_callback = drop_callback
        self.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.blue))
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        self._start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        target = self.pos()
        self.setPos(self._start_pos)
        if self.drop_callback:
            self.drop_callback(target)


class RealTimeBattleWidget(QtWidgets.QWidget):
    """Container widget for the real-time battle view."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Map canvas using QGraphicsView for extensibility.
        self.scene = QtWidgets.QGraphicsScene(self)
        self.map_canvas = QtWidgets.QGraphicsView(self.scene)
        layout.addWidget(self.map_canvas, 1)

        controls_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(controls_layout)

        # Placeholder for army control widgets
        self.army_controls = QtWidgets.QLabel("Army Controls")
        self.army_controls.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.army_controls, 1)

        # Refresh button used to update the map when in use
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        controls_layout.addWidget(self.refresh_button)

        # Load navmesh from bundled file and draw polygons
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

        # Army representation
        self.army_item = ArmyItem(5.0, self.move_army_to)
        self.scene.addItem(self.army_item)
        self.army_item.setPos(QtCore.QPointF(10, 10))
        self.army_logical_pos = QtCore.QPointF(10, 10)
        self.path: List[QtCore.QPointF] = []

        # Timers: interpolation at 1 ms and logic at 1 Hz
        self.logic_timer = QtCore.QTimer(self)
        self.logic_timer.timeout.connect(self._update_logic)
        self.logic_timer.start(1000)

        self.interp_timer = QtCore.QTimer(self)
        self.interp_timer.timeout.connect(self._update_interp)
        self.interp_timer.start(1)

        self.speed = 1.0  # units per second

    def move_army_to(self, target: QtCore.QPointF) -> None:
        """Move the army towards a target constrained to the navmesh."""
        start = (self.army_item.x(), self.army_item.y())
        target_tuple = (target.x(), target.y())
        if not self.navmesh.find_polygon(target_tuple):
            return
        path_points = self.navmesh.find_path(start, target_tuple)
        # Drop first point (current position) as the item already sits there
        self.path = [QtCore.QPointF(x, y) for x, y in path_points[1:]]

    def _update_interp(self) -> None:
        if not self.path:
            return
        current = self.army_item.pos()
        target = self.path[0]
        step = self.speed * 0.001
        dx = target.x() - current.x()
        dy = target.y() - current.y()
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step:
            self.army_item.setPos(target)
            self.path.pop(0)
        else:
            self.army_item.setPos(
                QtCore.QPointF(
                    current.x() + dx / dist * step,
                    current.y() + dy / dist * step,
                )
            )

    def _update_logic(self) -> None:
        # Logical position used for combat simulation at lower frequency
        self.army_logical_pos = self.army_item.pos()
