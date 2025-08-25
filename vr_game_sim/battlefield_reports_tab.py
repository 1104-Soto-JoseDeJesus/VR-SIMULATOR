"""Tab showing battle reports for armies on the battlefield."""
from __future__ import annotations

from PyQt6 import QtWidgets

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
        self._bf_tab.reportsUpdated.connect(self._populate)
        self._populate()

    def _populate(self) -> None:
        self._selector.blockSignals(True)
        self._selector.clear()
        for army in self._bf_tab.armies:
            self._selector.addItem(army.name)
        self._selector.blockSignals(False)
        self._refresh()

    def _refresh(self) -> None:
        idx = self._selector.currentIndex()
        if 0 <= idx < len(self._bf_tab.armies):
            army = self._bf_tab.armies[idx]
            self._text.setPlainText("\n\n".join(army.battle_reports))
        else:
            self._text.clear()
