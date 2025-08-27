from __future__ import annotations

"""Widget placeholder for real-time battle visualisation.

This widget provides a basic layout containing a map canvas, placeholder
area for army controls and a refresh button.  It is designed to be used as a
stand-alone tab within the main GUI so that loading it does not affect the
existing 1v1 figures tab.
"""

from PyQt6 import QtCore, QtWidgets


class RealTimeBattleWidget(QtWidgets.QWidget):
    """Container widget for the real-time battle view."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Map canvas placeholder.  Using QGraphicsView allows future extension
        # without altering the tab interface.
        self.map_canvas = QtWidgets.QGraphicsView()
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
