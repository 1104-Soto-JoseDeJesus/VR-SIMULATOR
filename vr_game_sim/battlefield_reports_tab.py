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
        self._selector = QtWidgets.QComboBox()
        self._selector.currentIndexChanged.connect(self._refresh)
        layout.addWidget(self._selector)
        self._text = QtWidgets.QPlainTextEdit(readOnly=True)
        layout.addWidget(self._text, 1)
        # Keep a persistent list of armies so reports remain even after death
        self._armies: list[Army] = []
        self._bf_tab.reportsUpdated.connect(self._update)
        self._update()

    def _update(self) -> None:
        """Refresh army list and currently displayed report."""
        # Track new armies but never remove old ones so logs persist
        for army in self._bf_tab.armies:
            if army not in self._armies:
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
