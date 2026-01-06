"""Placeholder GUI entry point for experimenting with a new interface.

This module intentionally keeps the existing GUI untouched while providing a
blank window that can be evolved independently. Launch it with
``python -m vr_game_sim.gui_main_v2``.
"""

from __future__ import annotations

import sys
import ctypes
from importlib import resources
from pathlib import Path
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets


def _load_window_icon() -> QtGui.QIcon:
    """Load the window icon after a QApplication exists."""

    packaged_icon = resources.files("vr_game_sim").joinpath(
        "Icons/Viking_Rise_Simulator_Icon.png"
    )
    local_icon = Path(__file__).with_name("Icons") / "Viking_Rise_Simulator_Icon.png"

    try:
        with resources.as_file(packaged_icon) as icon_path:
            resolved_path = icon_path if icon_path.exists() else local_icon
            if not resolved_path.exists():
                raise FileNotFoundError
            return QtGui.QIcon(str(resolved_path))
    except FileNotFoundError:
        if not local_icon.exists():
            raise FileNotFoundError(
                "Expected application icon missing. Ensure it is included with the package. "
                f"Checked {packaged_icon} and {local_icon}."
            )
        return QtGui.QIcon(str(local_icon))


def _resolve_background_image() -> str:
    """Return a filesystem path to the GUI v2 background image.

    Falls back to a local path if importlib resources cannot locate the asset.
    """

    packaged_background = resources.files("vr_game_sim").joinpath(
        "Icons/GUI_2_BACKGROUND.png"
    )
    local_background = Path(__file__).with_name("Icons") / "GUI_2_BACKGROUND.png"

    try:
        with resources.as_file(packaged_background) as background_path:
            resolved_path = background_path if background_path.exists() else local_background
            if not resolved_path.exists():
                raise FileNotFoundError
            return resolved_path.as_posix()
    except FileNotFoundError:
        if not local_background.exists():
            raise FileNotFoundError(
                "Expected GUI v2 background image missing. Ensure it is included with the package. "
                f"Checked {packaged_background} and {local_background}."
            )
        return local_background.as_posix()


def _ensure_windows_app_id() -> None:
    """Set a stable AppUserModelID so Windows picks up the custom taskbar icon."""

    if sys.platform != "win32":
        return

    app_id = "vr_game_sim.gui_v2"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)  # type: ignore[attr-defined]
    except OSError:
        # Best-effort: if setting fails we still allow the app to run.
        pass


class NavigationButton(QtWidgets.QPushButton):
    """Rounded navigation button with a subtle glow when selected."""

    def __init__(self, text: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 35, 45, 200);
                border: 1px solid rgba(90, 110, 140, 120);
                color: #e0e0e0;
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QPushButton:hover {
                border-color: rgba(88, 168, 255, 180);
                background-color: rgba(36, 43, 56, 220);
            }
            QPushButton:checked {
                background-color: rgba(40, 90, 140, 200);
                border: 1px solid #42a5f5;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(32, 70, 110, 200);
            }
            """
        )

        self._glow = QtWidgets.QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(22)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QtGui.QColor(66, 165, 245, 160))

        self.toggled.connect(self.refresh_glow)
        self.refresh_glow(self.isChecked())

    def refresh_glow(self, checked: Optional[bool] = None) -> None:
        active = self.isChecked() if checked is None else checked
        self.setGraphicsEffect(self._glow if active else None)


class PlaceholderWindow(QtWidgets.QMainWindow):
    """Minimal window used as a starting point for the new GUI."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        window_icon: Optional[QtGui.QIcon] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("VR Game Simulator - GUI v2 (Placeholder)")
        self.setMinimumSize(900, 600)
        if window_icon:
            self.setWindowIcon(window_icon)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        background_path = _resolve_background_image()
        scroll_area.viewport().setStyleSheet(
            "QWidget {"
            f"    background-image: url({background_path});"
            "    background-repeat: repeat;"
            "}"
        )

        placeholder = QtWidgets.QWidget(self)
        placeholder.setMinimumHeight(1200)

        layout = QtWidgets.QVBoxLayout(placeholder)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        navigation_bar = QtWidgets.QFrame(placeholder)
        navigation_bar.setObjectName("navigationBar")
        nav_layout = QtWidgets.QHBoxLayout(navigation_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(12)

        self._button_group = QtWidgets.QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._nav_buttons = []

        for label in ("Overview", "Army Mode", "Duel Mode", "Reports"):
            button = NavigationButton(label, navigation_bar)
            self._button_group.addButton(button)
            nav_layout.addWidget(button)
            self._nav_buttons.append(button)

        duel_button = next(
            (btn for btn in self._nav_buttons if btn.text() == "Duel Mode"), None
        )
        if duel_button:
            duel_button.setChecked(True)

        self._button_group.buttonClicked.connect(self._handle_nav_selected)

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

        description = QtWidgets.QLabel(
            "Use this space to prototype layout ideas, widgets, and navigation for "
            "the second-generation interface. The scrollable canvas repeats its "
            "background so you can explore longer flows without running into "
            "empty space.",
            placeholder,
        )
        description.setWordWrap(True)
        description.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(navigation_bar)
        layout.addStretch(1)
        layout.addWidget(heading)
        layout.addWidget(instructions)
        layout.addWidget(description)
        layout.addSpacing(600)
        layout.addStretch(1)

        scroll_area.setWidget(placeholder)
        self.setCentralWidget(scroll_area)

    def _handle_nav_selected(self, _: QtWidgets.QAbstractButton) -> None:
        for button in self._nav_buttons:
            button.refresh_glow()


def main() -> int:
    """Launch the placeholder GUI for the new interface."""

    _ensure_windows_app_id()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window_icon = _load_window_icon()
    app.setWindowIcon(window_icon)
    window = PlaceholderWindow(window_icon=window_icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
