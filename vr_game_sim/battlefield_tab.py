"""GUI tab for interacting with the multi-army battlefield."""
from __future__ import annotations

from typing import List
import copy

from PyQt6 import QtCore, QtWidgets, QtGui

from .battlefield import Battlefield
from .multi_army_simulator import MultiArmySimulator
from .army_composition import Army
from .main import create_armies_from_data


class BattlefieldGrid(QtWidgets.QTableWidget):
    """Custom table widget providing drag-and-drop army movement."""

    armyDropped = QtCore.pyqtSignal(int, int, int)
    armyClicked = QtCore.pyqtSignal(int)
    armyDoubleClicked = QtCore.pyqtSignal(int)

    def __init__(self, tab: "BattlefieldTab") -> None:
        super().__init__(tab.battlefield.height, tab.battlefield.width)
        self._tab = tab
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # Enable drag and drop handling on the table's viewport
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._drag_army_idx: int | None = None
        self._drag_start_pos: QtCore.QPointF | None = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            row = self.rowAt(int(event.position().y()))
            col = self.columnAt(int(event.position().x()))
            army = self._tab._army_at(col, row)
            if army:
                self._drag_army_idx = self._tab.armies.index(army)
                self._drag_start_pos = event.position()
                self.armyClicked.emit(self._drag_army_idx)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if (
            self._drag_army_idx is not None
            and self._drag_start_pos is not None
            and (event.position() - self._drag_start_pos).manhattanLength()
            > QtWidgets.QApplication.startDragDistance()
        ):
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            mime.setText(str(self._drag_army_idx))
            drag.setMimeData(mime)
            drag.exec(QtCore.Qt.DropAction.MoveAction)
            self._drag_army_idx = None
            self._drag_start_pos = None
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            idx = int(event.mimeData().text())
            row = self.rowAt(int(event.position().y()))
            col = self.columnAt(int(event.position().x()))
            self.armyDropped.emit(idx, col, row)
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        row = self.rowAt(int(event.position().y()))
        col = self.columnAt(int(event.position().x()))
        army = self._tab._army_at(col, row)
        if army:
            idx = self._tab.armies.index(army)
            self.armyDoubleClicked.emit(idx)
        super().mouseDoubleClickEvent(event)


class BattlefieldTab(QtWidgets.QWidget):
    """Widget to display and control a battlefield."""

    def __init__(self, main_window: 'MainWindow', width: int = 16, height: int = 16) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self.battlefield = Battlefield(width, height)
        self.armies: List[Army] = []
        self.army_configs: List[dict] = []
        self.simulator: MultiArmySimulator | None = None

        layout = QtWidgets.QVBoxLayout(self)

        # Grid representing the battlefield
        self.grid = BattlefieldGrid(self)
        self.grid.horizontalHeader().setVisible(False)
        self.grid.verticalHeader().setVisible(False)
        self.grid.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.grid.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.grid.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        for y in range(self.battlefield.height):
            for x in range(self.battlefield.width):
                item = QtWidgets.QTableWidgetItem("")
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.grid.setItem(y, x, item)
        self.grid.armyDropped.connect(self._drag_move)
        self.grid.armyClicked.connect(self._select_army_from_grid)
        self.grid.armyDoubleClicked.connect(self._edit_army)
        layout.addWidget(self.grid, 1)

        # Controls for issuing movement commands
        controls = QtWidgets.QHBoxLayout()
        layout.addLayout(controls)

        self.army_select = QtWidgets.QComboBox()
        controls.addWidget(self.army_select)

        self.x_spin = QtWidgets.QSpinBox()
        self.x_spin.setRange(0, self.battlefield.width - 1)
        controls.addWidget(self.x_spin)

        self.y_spin = QtWidgets.QSpinBox()
        self.y_spin.setRange(0, self.battlefield.height - 1)
        controls.addWidget(self.y_spin)

        move_btn = QtWidgets.QPushButton("Set Destination")
        move_btn.clicked.connect(self._set_destination)
        controls.addWidget(move_btn)

        step_btn = QtWidgets.QPushButton("Step")
        step_btn.clicked.connect(self._step)
        controls.addWidget(step_btn)

        reset_btn = QtWidgets.QPushButton("Reset from Setup")
        reset_btn.clicked.connect(self._reset_from_setup)
        controls.addWidget(reset_btn)

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
            self.battlefield.place_army(self.armies[1], self.battlefield.width - 1, self.battlefield.height - 1)
        self.simulator = MultiArmySimulator(self.battlefield, self.armies)
        self.army_select.clear()
        for army in self.armies:
            self.army_select.addItem(army.name)
        self._refresh_grid()

    def _set_destination(self) -> None:
        idx = self.army_select.currentIndex()
        if idx < 0 or idx >= len(self.armies):
            return
        dest = (self.x_spin.value(), self.y_spin.value())
        self.armies[idx].set_destination(dest)

    def _step(self) -> None:
        if not self.simulator:
            return
        self.simulator.step()
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        for y in range(self.battlefield.height):
            for x in range(self.battlefield.width):
                item = self.grid.item(y, x)
                if item is not None:
                    item.setText("")
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            if self.battlefield.within_bounds(army.x, army.y):
                item = self.grid.item(army.y, army.x)
                if item is not None:
                    item.setText(army.name[:1].upper())

    # ------------------------------------------------------------------
    def _army_at(self, x: int, y: int) -> Army | None:
        for army in self.armies:
            if army.current_troop_count > 0 and army.x == x and army.y == y:
                return army
        return None

    def _drag_move(self, idx: int, x: int, y: int) -> None:
        if 0 <= idx < len(self.armies):
            if self.battlefield.place_army(self.armies[idx], x, y):
                self.armies[idx].destination = None
                self._refresh_grid()

    def _select_army_from_grid(self, idx: int) -> None:
        if 0 <= idx < len(self.armies):
            self.army_select.setCurrentIndex(idx)
            army = self.armies[idx]
            self.x_spin.setValue(army.x)
            self.y_spin.setValue(army.y)

    def _edit_army(self, idx: int) -> None:
        if not (0 <= idx < len(self.armies)):
            return
        self._select_army_from_grid(idx)
        dialog = ArmyConfigDialog(self.army_configs[idx], self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dialog.build_config()
            self.army_configs[idx] = cfg
            x, y = self.armies[idx].x, self.armies[idx].y
            self.armies[idx] = create_armies_from_data([cfg])[0]
            self.battlefield.place_army(self.armies[idx], x, y)
            self.army_select.setItemText(idx, self.armies[idx].name)
            self._refresh_grid()


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

