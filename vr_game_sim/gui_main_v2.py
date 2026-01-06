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

from vr_game_sim.hero_definition import HERO_PRESETS


def _load_window_icon() -> QtGui.QIcon:
    """Load the window icon after a QApplication exists.

    Builds a multi-size QIcon to ensure Windows taskbar and title bar pick up the
    custom artwork instead of a generic placeholder.
    """

    packaged_icon = resources.files("vr_game_sim").joinpath(
        "Icons/Viking_Rise_Simulator_Icon.png"
    )
    local_icon = Path(__file__).with_name("Icons") / "Viking_Rise_Simulator_Icon.png"

    try:
        with resources.as_file(packaged_icon) as icon_path:
            resolved_path = icon_path if icon_path.exists() else local_icon
            if not resolved_path.exists():
                raise FileNotFoundError
            pixmap = QtGui.QPixmap(str(resolved_path))
    except FileNotFoundError:
        if not local_icon.exists():
            raise FileNotFoundError(
                "Expected application icon missing. Ensure it is included with the package. "
                f"Checked {packaged_icon} and {local_icon}."
            )
        pixmap = QtGui.QPixmap(str(local_icon))

    if pixmap.isNull():
        raise FileNotFoundError(
            "Application icon failed to load. Confirm Viking_Rise_Simulator_Icon.png is accessible."
        )

    icon = QtGui.QIcon()
    for size in (16, 24, 32, 48, 64, 96, 128, 256):
        icon.addPixmap(
            pixmap.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        )

    return icon


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
                background-color: transparent;
                border: 1px solid rgba(90, 110, 140, 150);
                color: #e0e0e0;
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QPushButton:hover {
                border-color: rgba(88, 168, 255, 200);
                background-color: rgba(66, 165, 245, 40);
            }
            QPushButton:checked {
                background-color: rgba(66, 165, 245, 60);
                border: 1px solid #42a5f5;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(66, 165, 245, 70);
            }
            """
        )

        self._glow = QtWidgets.QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(22)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QtGui.QColor(66, 165, 245, 160))
        self.setGraphicsEffect(self._glow)

        self.toggled.connect(self.refresh_glow)
        self.refresh_glow(self.isChecked())

    def refresh_glow(self, checked: Optional[bool] = None) -> None:
        active = self.isChecked() if checked is None else checked
        self._glow.setEnabled(active)
        glow_color = QtGui.QColor(66, 165, 245, 160 if active else 0)
        self._glow.setColor(glow_color)


class NavigationOptionButton(QtWidgets.QPushButton):
    """Secondary navigation option aligned with the dark theme."""

    def __init__(self, text: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: 1px solid rgba(70, 90, 120, 150);
                color: #d5d8df;
                border-radius: 10px;
                padding: 8px 14px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(66, 165, 245, 35);
                border-color: rgba(88, 168, 255, 200);
            }
            QPushButton:checked {
                background-color: rgba(66, 165, 245, 50);
                border-color: rgba(88, 168, 255, 220);
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(66, 165, 245, 70);
            }
            """
        )


class CollapsibleNavSection(QtWidgets.QWidget):
    """Container with a main navigation button and collapsible options."""

    option_clicked = QtCore.pyqtSignal(str, str)

    def __init__(self, title: str, options: list[str], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.title = title
        self._option_buttons: list[NavigationOptionButton] = []

        self.header_button = NavigationButton(title, self)
        self.header_button.setChecked(False)

        self._content = QtWidgets.QWidget(self)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(12, 4, 4, 12)
        content_layout.setSpacing(6)

        for option in options:
            button = NavigationOptionButton(option, self._content)
            content_layout.addWidget(button)
            button.clicked.connect(lambda _checked=False, opt=option: self.option_clicked.emit(self.title, opt))
            self._option_buttons.append(button)

        self._content.setVisible(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.header_button)
        layout.addWidget(self._content)

        self.header_button.toggled.connect(self._toggle_content)

    def clear_option_selection(self) -> None:
        for button in self._option_buttons:
            button.setChecked(False)

    def set_option_checked(self, option: str) -> None:
        for button in self._option_buttons:
            button.setChecked(button.text() == option)

    def _toggle_content(self, checked: bool) -> None:
        self._content.setVisible(checked)


class ArmySetupSection(QtWidgets.QGroupBox):
    """Input cluster for configuring one army in duel mode."""

    name_changed = QtCore.pyqtSignal(str)

    UNIT_ICON_MAP = {
        "Pikemen": "Pikemen_Selection.png",
        "Archers": "Archer_Selection.png",
        "Infantry": "Infantry_Selection.png",
    }

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)
        self.setStyleSheet(
            """
            QGroupBox {
                color: #d5d8df;
                border: 1px solid rgba(70, 90, 120, 140);
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: rgba(12, 16, 24, 160);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px 0 4px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: transparent;
                color: #e0e5ee;
                border: 1px solid rgba(90, 110, 140, 160);
                border-radius: 6px;
                padding: 6px 8px;
                selection-background-color: rgba(66, 165, 245, 120);
                selection-color: #0a0e16;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #42a5f5;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: transparent;
            }
            QComboBox::drop-down, QComboBox::down-arrow {
                background-color: transparent;
            }
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(12)

        self.army_name = QtWidgets.QLineEdit(self)
        self.army_name.setPlaceholderText("Army name")
        self.army_name.textChanged.connect(self._emit_name_changed)
        layout.addWidget(self.army_name)

        layout.addLayout(self._build_unit_row())
        layout.addLayout(self._build_stats_row())
        layout.addLayout(self._build_hero_row())

    def _build_unit_row(self) -> QtWidgets.QLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)

        unit_layout = QtWidgets.QVBoxLayout()
        unit_layout.setSpacing(6)
        unit_label = QtWidgets.QLabel("Unit selection", self)
        unit_label.setStyleSheet("font-weight: 600; color: #e0e5ee;")
        unit_layout.addWidget(unit_label)

        icon_row = QtWidgets.QHBoxLayout()
        icon_row.setSpacing(8)
        self._unit_group = QtWidgets.QButtonGroup(self)
        self._unit_group.setExclusive(True)
        for unit, icon_name in self.UNIT_ICON_MAP.items():
            button = QtWidgets.QToolButton(self)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setIcon(self._load_unit_icon(icon_name))
            button.setIconSize(QtCore.QSize(52, 52))
            button.setToolTip(unit)
            self._unit_group.addButton(button)
            icon_row.addWidget(button)
        if self._unit_group.buttons():
            self._unit_group.buttons()[0].setChecked(True)
        unit_layout.addLayout(icon_row)

        row.addLayout(unit_layout)

        tier_layout = QtWidgets.QVBoxLayout()
        tier_layout.setSpacing(6)
        tier_label = QtWidgets.QLabel("Tier (4-7)", self)
        tier_label.setStyleSheet("font-weight: 600; color: #e0e5ee;")
        self.tier_input = QtWidgets.QSpinBox(self)
        self.tier_input.setRange(4, 7)
        self.tier_input.setValue(7)
        self.tier_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.PlusMinus)
        tier_layout.addWidget(tier_label)
        tier_layout.addWidget(self.tier_input)

        row.addLayout(tier_layout)
        row.addStretch(1)
        return row

    def _build_stats_row(self) -> QtWidgets.QLayout:
        row = QtWidgets.QGridLayout()
        row.setHorizontalSpacing(12)
        row.setVerticalSpacing(8)

        troop_label = QtWidgets.QLabel("Troop count", self)
        self.troop_count = QtWidgets.QSpinBox(self)
        self.troop_count.setRange(0, 10_000_000)
        self.troop_count.setSingleStep(1000)

        atk_label = QtWidgets.QLabel("Attack mod", self)
        self.attack_mod = QtWidgets.QDoubleSpinBox(self)
        self.attack_mod.setRange(-500.0, 500.0)
        self.attack_mod.setDecimals(2)
        self.attack_mod.setSuffix(" %")

        def_label = QtWidgets.QLabel("Defense mod", self)
        self.defense_mod = QtWidgets.QDoubleSpinBox(self)
        self.defense_mod.setRange(-500.0, 500.0)
        self.defense_mod.setDecimals(2)
        self.defense_mod.setSuffix(" %")

        hp_label = QtWidgets.QLabel("HP mod", self)
        self.hp_mod = QtWidgets.QDoubleSpinBox(self)
        self.hp_mod.setRange(-500.0, 500.0)
        self.hp_mod.setDecimals(2)
        self.hp_mod.setSuffix(" %")

        heavy_label = QtWidgets.QLabel("Heavily wounded ratio", self)
        self.heavy_ratio = QtWidgets.QComboBox(self)
        self.heavy_ratio.addItem("Dynamic")
        for pct in range(0, 101, 10):
            self.heavy_ratio.addItem(f"{pct}%")

        row.addWidget(troop_label, 0, 0)
        row.addWidget(self.troop_count, 0, 1)
        row.addWidget(atk_label, 0, 2)
        row.addWidget(self.attack_mod, 0, 3)
        row.addWidget(def_label, 1, 0)
        row.addWidget(self.defense_mod, 1, 1)
        row.addWidget(hp_label, 1, 2)
        row.addWidget(self.hp_mod, 1, 3)
        row.addWidget(heavy_label, 2, 0)
        row.addWidget(self.heavy_ratio, 2, 1)
        row.setColumnStretch(4, 1)

        return row

    def _build_hero_row(self) -> QtWidgets.QLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)

        label = QtWidgets.QLabel("Hero selection", self)
        label.setStyleSheet("font-weight: 600; color: #e0e5ee;")
        row.addWidget(label)

        self.hero_primary = QtWidgets.QComboBox(self)
        self.hero_secondary = QtWidgets.QComboBox(self)
        for combo in (self.hero_primary, self.hero_secondary):
            combo.setEditable(False)
            combo.setMinimumWidth(160)
            combo.currentTextChanged.connect(self._update_name_from_hero)
        row.addWidget(self.hero_primary)
        row.addWidget(self.hero_secondary)
        row.addStretch(1)
        return row

    def populate_heroes(self, heroes: list[str]) -> None:
        for combo in (self.hero_primary, self.hero_secondary):
            combo.clear()
            combo.addItem("Select hero")
            combo.addItems(heroes)

    def set_army_name(self, name: str, *, emit_signal: bool = True) -> None:
        was_blocked = self.army_name.blockSignals(True)
        self.army_name.setText(name)
        self.army_name.blockSignals(was_blocked)
        if emit_signal:
            self._emit_name_changed(name)

    def _emit_name_changed(self, name: str) -> None:
        self.name_changed.emit(name)

    def _update_name_from_hero(self, _text: str) -> None:
        hero_candidates = (
            self.hero_primary.currentText(),
            self.hero_secondary.currentText(),
        )
        hero_name = next((name for name in hero_candidates if name != "Select hero"), "")
        if hero_name:
            self.set_army_name(hero_name)

    def _load_unit_icon(self, icon_name: str) -> QtGui.QIcon:
        packaged_icon = resources.files("vr_game_sim").joinpath(f"Icons/{icon_name}")
        local_icon = Path(__file__).with_name("Icons") / icon_name
        try:
            with resources.as_file(packaged_icon) as icon_path:
                resolved_path = icon_path if icon_path.exists() else local_icon
        except FileNotFoundError:
            resolved_path = local_icon

        pixmap = QtGui.QPixmap(str(resolved_path)) if resolved_path.exists() else QtGui.QPixmap()
        if pixmap.isNull():
            placeholder = QtGui.QPixmap(52, 52)
            placeholder.fill(QtGui.QColor("#4a5568"))
            return QtGui.QIcon(placeholder)
        return QtGui.QIcon(pixmap)


class ArmySetupView(QtWidgets.QWidget):
    """Duel mode army setup view with mirrored army inputs."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        heading = QtWidgets.QLabel("Duel Mode • Army setup", self)
        heading.setStyleSheet("font-size: 20px; font-weight: 700; color: #f5f7fb;")
        layout.addWidget(heading)

        subtext = QtWidgets.QLabel(
            "Configure both armies before running a duel simulation. Each side can "
            "select units, tiers, troop counts, stat modifiers, wounded ratios, and heroes.",
            self,
        )
        subtext.setWordWrap(True)
        layout.addWidget(subtext)

        grid = QtWidgets.QHBoxLayout()
        grid.setSpacing(16)

        self.army_a = ArmySetupSection("Army A", self)
        self.army_b = ArmySetupSection("Army B", self)
        self.army_a.name_changed.connect(lambda name: self._ensure_unique_army_names(self.army_a, name))
        self.army_b.name_changed.connect(lambda name: self._ensure_unique_army_names(self.army_b, name))
        grid.addWidget(self.army_a)
        grid.addWidget(self.army_b)

        layout.addLayout(grid)
        layout.addStretch(1)

    def populate_heroes(self, heroes: list[str]) -> None:
        self.army_a.populate_heroes(heroes)
        self.army_b.populate_heroes(heroes)

    def _ensure_unique_army_names(self, changed_section: ArmySetupSection, new_name: str) -> None:
        normalized = new_name.strip()
        if not normalized:
            return

        other_section = self.army_b if changed_section is self.army_a else self.army_a
        other_name = other_section.army_name.text().strip()

        if normalized == other_name:
            other_section.set_army_name(f"{normalized} 2", emit_signal=False)


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

        canvas = QtWidgets.QWidget(self)
        canvas.setMinimumHeight(800)

        layout = QtWidgets.QVBoxLayout(canvas)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(18)

        navigation_bar = QtWidgets.QFrame(canvas)
        navigation_bar.setObjectName("navigationBar")
        navigation_bar.setMaximumWidth(self.minimumWidth())
        navigation_bar.setStyleSheet(
            """
            QFrame#navigationBar {
                background-color: transparent;
                border: 1px solid rgba(70, 90, 120, 140);
                border-radius: 14px;
            }
            """
        )

        nav_layout = QtWidgets.QHBoxLayout(navigation_bar)
        nav_layout.setContentsMargins(16, 16, 16, 16)
        nav_layout.setSpacing(12)

        nav_groups = {
            "Duel Mode": ["Army setup", "Report", "Figures", "Skill Breakdowns"],
            "Battlefield Mode": ["Battle field", "Battlefield Reports"],
            "Arena Mode": ["Arena", "Arena Reports", "Arena Figures"],
        }

        self._nav_sections: list[CollapsibleNavSection] = []
        for title, options in nav_groups.items():
            section = CollapsibleNavSection(title, options, navigation_bar)
            section.header_button.setChecked(title == "Duel Mode")
            section.option_clicked.connect(self._handle_option_clicked)
            nav_layout.addWidget(section)
            self._nav_sections.append(section)

        nav_layout.addStretch(1)

        content_frame = QtWidgets.QFrame(canvas)
        content_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(10, 14, 22, 200);
                border: 1px solid rgba(70, 90, 120, 110);
                border-radius: 16px;
            }
            """
        )

        content_layout = QtWidgets.QVBoxLayout(content_frame)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        self._main_stack = QtWidgets.QStackedWidget(content_frame)
        self._pages: dict[str, int] = {}

        welcome_page = self._build_welcome_page(content_frame)
        self._pages["Welcome"] = self._main_stack.addWidget(welcome_page)

        self.army_setup_view = ArmySetupView(content_frame)
        self.army_setup_view.populate_heroes(self._load_hero_names())
        self._pages["Army setup"] = self._main_stack.addWidget(self.army_setup_view)

        content_layout.addWidget(self._main_stack)

        layout.addWidget(
            navigation_bar, alignment=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        layout.addWidget(content_frame)

        scroll_area.setWidget(canvas)
        self.setCentralWidget(scroll_area)

        self._handle_option_clicked("Duel Mode", "Army setup")

    def _build_welcome_page(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        heading = QtWidgets.QLabel("New GUI - Work in Progress", page)
        heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        heading.setStyleSheet("font-size: 20px; font-weight: bold; color: #f5f7fb;")
        layout.addWidget(heading)

        instructions = QtWidgets.QLabel(
            "Use the navigation above to switch between duel, battlefield, and arena flows. "
            "We'll populate each view as new designs come online.",
            page,
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        description = QtWidgets.QLabel(
            "Click 'Army setup' under Duel Mode to start configuring two opposing armies.",
            page,
        )
        description.setWordWrap(True)
        description.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(instructions)
        layout.addWidget(description)
        layout.addStretch(1)
        return page

    def _handle_option_clicked(self, section_title: str, option: str) -> None:
        for section in self._nav_sections:
            if section.title == section_title:
                section.header_button.setChecked(True)
                section.set_option_checked(option)
            else:
                section.clear_option_selection()

        if option in self._pages:
            self._main_stack.setCurrentIndex(self._pages[option])
        else:
            placeholder_index = self._ensure_placeholder_page(option)
            self._main_stack.setCurrentIndex(placeholder_index)

    def _ensure_placeholder_page(self, option: str) -> int:
        if option in self._pages:
            return self._pages[option]

        page = QtWidgets.QWidget(self._main_stack)
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        label = QtWidgets.QLabel(f"{option} is coming soon.", page)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        label.setStyleSheet("font-size: 18px; font-weight: 600; color: #e0e5ee;")
        layout.addWidget(label)

        body = QtWidgets.QLabel(
            "We're filling in each section one by one. Check back after the duel mode "
            "army setup is complete.",
            page,
        )
        body.setWordWrap(True)
        body.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(body)
        layout.addStretch(1)

        index = self._main_stack.addWidget(page)
        self._pages[option] = index
        return index

    def _load_hero_names(self) -> list[str]:
        readable = [name.replace("_", " ").title() for name in HERO_PRESETS.keys()]
        return sorted(readable)

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
