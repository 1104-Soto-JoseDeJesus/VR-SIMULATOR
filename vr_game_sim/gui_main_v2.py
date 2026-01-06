"""Placeholder GUI entry point for experimenting with a new interface.

This module intentionally keeps the existing GUI untouched while providing a
blank window that can be evolved independently. Launch it with
``python -m vr_game_sim.gui_main_v2``.
"""

from __future__ import annotations

import sys
from typing import Optional

from PyQt6 import QtCore, QtWidgets


class PlaceholderWindow(QtWidgets.QMainWindow):
    """Minimal window used as a starting point for the new GUI."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VR Game Simulator - GUI v2 (Placeholder)")
        self.setMinimumSize(900, 600)

        placeholder = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(placeholder)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        heading = QtWidgets.QLabel("New GUI - Work in Progress", placeholder)
        heading.setObjectName("placeholderHeading")
        heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")

        instructions = QtWidgets.QLabel(
            "This window is intentionally blank so we can iteratively build "
            "the new interface without affecting the legacy GUI.",
            placeholder,
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)
        layout.addWidget(heading)
        layout.addWidget(instructions)
        layout.addStretch(1)

        self.setCentralWidget(placeholder)


def main() -> int:
    """Launch the placeholder GUI for the new interface."""

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = PlaceholderWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
