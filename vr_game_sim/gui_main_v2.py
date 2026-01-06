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

        layout.addStretch(1)
        layout.addWidget(heading)
        layout.addWidget(instructions)
        layout.addWidget(description)
        layout.addSpacing(600)
        layout.addStretch(1)

        scroll_area.setWidget(placeholder)
        self.setCentralWidget(scroll_area)


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
