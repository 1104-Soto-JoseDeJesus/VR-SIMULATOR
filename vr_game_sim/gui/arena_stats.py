from __future__ import annotations

import os

from PyQt6 import QtCore, QtGui, QtWidgets


STYLES_LOADED = False


def load_styles() -> None:
    """Load QSS styles for arena stats widgets."""
    global STYLES_LOADED
    if STYLES_LOADED:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    path = os.path.join(os.path.dirname(__file__), "styles.qss")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            app.setStyleSheet(app.styleSheet() + fh.read())
        STYLES_LOADED = True
    except OSError:
        pass


class HeroStatsHeader(QtWidgets.QWidget):
    """Header row that labels hero statistics columns."""

    def __init__(
        self, align_right: bool = False, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        load_styles()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        portrait_spacer = QtWidgets.QWidget()
        name_spacer = QtWidgets.QWidget()

        if align_right:
            headers = [("Kills", 0), ("Heals", 1), ("Remaining Troops", 2)]
            layout.addWidget(name_spacer, 0, 3)
            layout.addWidget(portrait_spacer, 0, 4)
            portrait_col = 4
        else:
            headers = [("Remaining Troops", 2), ("Heals", 3), ("Kills", 4)]
            layout.addWidget(portrait_spacer, 0, 0)
            layout.addWidget(name_spacer, 0, 1)
            portrait_col = 0

        icon_map = {
            "Heals": "HealsICON.png",
            "Kills": "KillsICON.png",
            "Remaining Troops": "RemainingTroopsICON.png",
        }

        for text, col in headers:
            container = QtWidgets.QWidget()
            vbox = QtWidgets.QVBoxLayout(container)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(2)
            vbox.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignHCenter
                | QtCore.Qt.AlignmentFlag.AlignBottom
            )

            icon_lbl = QtWidgets.QLabel()
            icon_path = os.path.join(
                os.path.dirname(__file__), "..", "Icons", icon_map[text]
            )
            pix = QtGui.QPixmap(icon_path)
            if not pix.isNull():
                size = int(QtGui.QFontMetrics(self.font()).height() * 2)
                icon_lbl.setPixmap(
                    pix.scaled(
                        size,
                        size,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
            icon_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            text_lbl = QtWidgets.QLabel(text)
            text_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            vbox.addWidget(icon_lbl)
            vbox.addWidget(text_lbl)

            layout.addWidget(
                container,
                0,
                col,
                alignment=
                QtCore.Qt.AlignmentFlag.AlignHCenter
                | QtCore.Qt.AlignmentFlag.AlignBottom,
            )
            layout.setColumnStretch(col, 1)

        if align_right:
            name_col = 3
            bar_cols = [0, 1, 2]
        else:
            name_col = 1
            bar_cols = [2, 3, 4]

        layout.setColumnStretch(portrait_col, 1)
        layout.setColumnStretch(name_col, 2)
        for col in bar_cols:
            layout.setColumnStretch(col, 3)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )


class HeroStatsWidget(QtWidgets.QWidget):
    """Display summary statistics for a hero in the arena."""

    def __init__(
        self,
        portrait_path: str,
        portrait2_path: str,
        name: str,
        remaining: int,
        initial: int,
        healed: int,
        kills: int,
        max_healed: int,
        max_kills: int,
        team_color: str,
        align_right: bool = False,
        hero_names: list[str] | None = None,
        skills: list[list[dict]] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_styles()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self.setProperty("team", team_color.lower())
        self._hero_names = hero_names or []
        self._skills = skills or []
        self._total_kills = kills
        self._total_healed = healed
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        portrait_container = QtWidgets.QWidget()
        portrait_layout = QtWidgets.QHBoxLayout(portrait_container)
        portrait_layout.setContentsMargins(0, 0, 0, 0)
        portrait_layout.setSpacing(0)

        self._portrait_labels: list[QtWidgets.QLabel] = []
        self._portrait_pixmaps: list[QtGui.QPixmap] = []
        for idx, path in enumerate((portrait_path, portrait2_path)):
            lbl = QtWidgets.QLabel()
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            pix = QtGui.QPixmap(path)
            if pix.isNull():
                lbl.setText("No\nImage")
                lbl.setStyleSheet("background-color: #444; color: white;")
            else:
                self._portrait_pixmaps.append(pix)
                lbl.setPixmap(pix)
            lbl.installEventFilter(self)
            lbl.setProperty("hero_index", idx)
            self._portrait_labels.append(lbl)
            portrait_layout.addWidget(lbl)

        font = QtGui.QFont()
        font.setPointSize(10)

        name_label = QtWidgets.QLabel(name)
        name_label.setFont(font)
        remaining_bar = QtWidgets.QProgressBar()
        remaining_bar.setRange(0, max(1, initial))
        remaining_bar.setValue(max(0, remaining))
        remaining_bar.setFormat(f"{remaining}/{initial}")
        remaining_bar.setProperty("class", "remaining")
        remaining_bar.setFont(font)

        self._anim = QtCore.QPropertyAnimation(remaining_bar, b"value", self)
        self._anim.setDuration(500)
        self._anim.setStartValue(0)
        self._anim.setEndValue(max(0, remaining))
        self._anim.start()

        healed_bar = QtWidgets.QProgressBar()
        healed_bar.setRange(0, max(1, max_healed))
        healed_bar.setValue(max(0, healed))
        healed_bar.setFormat(str(healed))
        healed_bar.setProperty("class", "healed")
        healed_bar.setFont(font)

        kills_bar = QtWidgets.QProgressBar()
        kills_bar.setRange(0, max(1, max_kills))
        kills_bar.setValue(max(0, kills))
        kills_bar.setFormat(str(kills))
        kills_bar.setProperty("class", "kills")
        kills_bar.setFont(font)

        if align_right:
            widgets = [
                kills_bar,
                healed_bar,
                remaining_bar,
                name_label,
                portrait_container,
            ]
            name_align = QtCore.Qt.AlignmentFlag.AlignRight
        else:
            widgets = [
                portrait_container,
                name_label,
                remaining_bar,
                healed_bar,
                kills_bar,
            ]
            name_align = QtCore.Qt.AlignmentFlag.AlignLeft

        for col, widget in enumerate(widgets):
            if widget is name_label:
                widget.setAlignment(name_align | QtCore.Qt.AlignmentFlag.AlignVCenter)
            elif isinstance(widget, QtWidgets.QProgressBar):
                widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            elif isinstance(widget, QtWidgets.QLabel):
                widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(widget, 0, col)
            layout.setColumnStretch(col, 1)

        if align_right:
            name_col = 3
            bar_cols = [0, 1, 2]
        else:
            name_col = 1
            bar_cols = [2, 3, 4]

        layout.setColumnStretch(name_col, 2)
        for col in bar_cols:
            layout.setColumnStretch(col, 3)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        size = int(self.height() * 0.9)
        for lbl in self._portrait_labels:
            lbl.setFixedSize(size, size)
        for lbl, pix in zip(self._portrait_labels, self._portrait_pixmaps):
            if not pix.isNull():
                lbl.setPixmap(
                    pix.scaled(
                        lbl.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
        super().resizeEvent(event)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        if (
            event.type() == QtCore.QEvent.Type.MouseButtonDblClick
            and obj in self._portrait_labels
        ):
            idx = obj.property("hero_index")
            try:
                index = int(idx)
            except (TypeError, ValueError):
                index = 0
            skills = self._skills[index] if index < len(self._skills) else []
            hero_name = self._hero_names[index] if index < len(self._hero_names) else "Hero"

            # Compute the total shield applied to the entire army across all skills
            total_shielded = sum(
                s.get("shielded", 0)
                for skill_list in self._skills
                for s in (skill_list or [])
            )

            dlg = HeroSkillDialog(
                hero_name,
                skills,
                self._total_kills,
                self._total_healed,
                total_shielded,
                self,
            )
            dlg.exec()
            return True
        return super().eventFilter(obj, event)


class ArenaStatsHeader(QtWidgets.QWidget):
    """Header for arena stats with two mirrored sides."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(HeroStatsHeader())
        layout.addWidget(HeroStatsHeader(align_right=True))


class ArenaStatsRow(QtWidgets.QWidget):
    """Row showing stats for a pair of heroes."""

    def __init__(
        self,
        left: dict | None,
        right: dict | None,
        max_healed: int,
        max_kills: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if left:
            left_widget = HeroStatsWidget(
                left.get("portrait1", ""),
                left.get("portrait2", ""),
                left.get("name", ""),
                left.get("remaining", 0),
                left.get("initial", left.get("remaining", 0)),
                left.get("healed", 0),
                left.get("kills", 0),
                max_healed,
                max_kills,
                left.get("team", "red"),
                hero_names=left.get("hero_names"),
                skills=left.get("skills"),
            )
        else:
            left_widget = QtWidgets.QWidget()
        layout.addWidget(left_widget)

        if right:
            right_widget = HeroStatsWidget(
                right.get("portrait1", ""),
                right.get("portrait2", ""),
                right.get("name", ""),
                right.get("remaining", 0),
                right.get("initial", right.get("remaining", 0)),
                right.get("healed", 0),
                right.get("kills", 0),
                max_healed,
                max_kills,
                right.get("team", "blue"),
                align_right=True,
                hero_names=right.get("hero_names"),
                skills=right.get("skills"),
            )
        else:
            right_widget = QtWidgets.QWidget()
        layout.addWidget(right_widget)


class SkillStatsRow(QtWidgets.QWidget):
    """Row showing statistics for a single skill."""

    def __init__(
        self,
        data: dict,
        total_kills: int,
        total_healed: int,
        total_shielded: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self._name = data.get("name", "")
        self._description = data.get("description", "")

        name_lbl = ClickableLabel(self._name)
        name_lbl.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        name_lbl.clicked.connect(self._show_description)
        layout.addWidget(name_lbl, 0, 0)

        cast_icon = QtWidgets.QLabel()
        cast_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "CastsICON.png"
        )
        cast_pix = QtGui.QPixmap(cast_path)
        size = int(QtGui.QFontMetrics(self.font()).height() * 1.5)
        if not cast_pix.isNull():
            cast_icon.setPixmap(
                cast_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(cast_icon, 0, 1)

        cast_lbl = QtWidgets.QLabel(str(data.get("casts", 0)))
        layout.addWidget(cast_lbl, 0, 2)

        kills_icon = QtWidgets.QLabel()
        kills_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "KillsICON.png"
        )
        kills_pix = QtGui.QPixmap(kills_path)
        if not kills_pix.isNull():
            kills_icon.setPixmap(
                kills_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(kills_icon, 0, 3)

        kills_bar = QtWidgets.QProgressBar()
        kills_bar.setRange(0, max(1, total_kills))
        kills_bar.setValue(data.get("kills", 0))
        kills_bar.setFormat(str(data.get("kills", 0)))
        kills_bar.setProperty("class", "kills")
        layout.addWidget(kills_bar, 0, 4)

        heals_icon = QtWidgets.QLabel()
        heals_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "HealsICON.png"
        )
        heals_pix = QtGui.QPixmap(heals_path)
        if not heals_pix.isNull():
            heals_icon.setPixmap(
                heals_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(heals_icon, 0, 5)

        heals_bar = QtWidgets.QProgressBar()
        heals_bar.setRange(0, max(1, total_healed))
        heals_bar.setValue(data.get("heals", 0))
        heals_bar.setFormat(str(data.get("heals", 0)))
        heals_bar.setProperty("class", "healed")
        layout.addWidget(heals_bar, 0, 6)

        shield_icon = QtWidgets.QLabel()
        shield_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "Shields.png"
        )
        shield_pix = QtGui.QPixmap(shield_path)
        if not shield_pix.isNull():
            shield_icon.setPixmap(
                shield_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(shield_icon, 0, 7)

        shield_bar = QtWidgets.QProgressBar()
        shield_bar.setRange(0, max(1, total_shielded))
        shield_bar.setValue(data.get("shielded", 0))
        shield_bar.setFormat(str(data.get("shielded", 0)))
        shield_bar.setProperty("class", "shielded")
        layout.addWidget(shield_bar, 0, 8)

        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(4, 3)
        layout.setColumnStretch(6, 3)
        layout.setColumnStretch(8, 3)

    def _show_description(self) -> None:
        if self._description:
            QtWidgets.QMessageBox.information(self, self._name, self._description)


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HeroSkillDialog(QtWidgets.QDialog):
    """Dialog displaying skill performance for a hero."""

    def __init__(
        self,
        hero_name: str,
        skills: list[dict],
        total_kills: int,
        total_healed: int,
        total_shielded: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_styles()
        self.setWindowTitle(f"{hero_name} Skill Breakdown")
        layout = QtWidgets.QVBoxLayout(self)
        for data in skills:
            layout.addWidget(SkillStatsRow(data, total_kills, total_healed, total_shielded))
        self.setLayout(layout)

