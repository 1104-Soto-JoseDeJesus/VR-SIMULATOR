"""Tab showing battle reports for armies on the battlefield."""
from __future__ import annotations

from PyQt6 import QtWidgets

from .army_composition import Army
from .battlefield_tab import BattlefieldTab


class BattlefieldReportsTab(QtWidgets.QWidget):
    """Display collected battle reports for each army."""

    def __init__(self, bf_tab: BattlefieldTab) -> None:
        super().__init__(bf_tab)
        self._bf_tab = bf_tab
        layout = QtWidgets.QVBoxLayout(self)
        control_row = QtWidgets.QHBoxLayout()
        self._selector = QtWidgets.QComboBox()
        self._selector.currentIndexChanged.connect(self._refresh)
        control_row.addWidget(self._selector, 1)
        clear_btn = QtWidgets.QPushButton("Clear Reports")
        clear_btn.clicked.connect(self._clear_reports)
        control_row.addWidget(clear_btn)
        layout.addLayout(control_row)
        self._text = QtWidgets.QPlainTextEdit(readOnly=True)
        layout.addWidget(self._text, 1)
        # Keep a persistent list of armies so reports remain even after death
        self._armies: list[Army] = []
        self._bf_tab.reportsUpdated.connect(self._update)
        self._update()

    def _update(self) -> None:
        """Refresh army list and currently displayed report."""
        # Track new armies but never remove old ones so logs persist. If an
        # existing army object is replaced (e.g. after editing), update the
        # reference instead of adding a duplicate entry.
        for army in self._bf_tab.armies:
            for i, existing in enumerate(self._armies):
                if existing.name == army.name:
                    self._armies[i] = army
                    break
            else:
                self._armies.append(army)
                self._selector.addItem(army.name)
        self._refresh()

    def _refresh(self) -> None:
        idx = self._selector.currentIndex()
        if 0 <= idx < len(self._armies):
            army = self._armies[idx]
            sb = self._text.verticalScrollBar()
            prev_max = sb.maximum()
            prev_val = sb.value()
            self._text.setPlainText("\n\n".join(army.battle_reports))
            # Preserve relative scroll position unless viewer was at bottom
            if prev_val == prev_max:
                sb.setValue(sb.maximum())
            else:
                sb.setValue(max(0, sb.maximum() - (prev_max - prev_val)))
        else:
            self._text.clear()

    def _clear_reports(self) -> None:
        """Remove all stored battle reports and prune dead armies."""
        alive: list[Army] = []
        self._selector.clear()
        for army in self._armies:
            if army.current_troop_count > 0:
                army.battle_reports.clear()
                alive.append(army)
                self._selector.addItem(army.name)
        self._armies = alive
        self._refresh()
