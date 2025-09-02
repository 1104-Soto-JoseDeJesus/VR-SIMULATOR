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


class SkillStatWidget(QtWidgets.QWidget):
    """Visualise cast counts, kills and heals for a single skill."""

    def __init__(
        self,
        name: str,
        casts: int,
        kills: int,
        heals: int,
        max_kills: int,
        max_heals: int,
        show_heals: bool = True,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_styles()

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)

        name_lbl = QtWidgets.QLabel(name)
        vbox.addWidget(name_lbl)

        cast_row = QtWidgets.QHBoxLayout()
        cast_icon = QtWidgets.QLabel()
        cast_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "CastsICON.png"
        )
        cast_pix = QtGui.QPixmap(cast_path)
        if not cast_pix.isNull():
            size = int(QtGui.QFontMetrics(self.font()).height() * 1.5)
            cast_icon.setPixmap(
                cast_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        cast_row.addWidget(cast_icon)
        cast_row.addWidget(QtWidgets.QLabel(str(casts)))
        cast_row.addStretch()
        vbox.addLayout(cast_row)

        kill_row = QtWidgets.QHBoxLayout()
        kill_icon = QtWidgets.QLabel()
        kill_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "KillsICON.png"
        )
        kill_pix = QtGui.QPixmap(kill_path)
        if not kill_pix.isNull():
            size = int(QtGui.QFontMetrics(self.font()).height() * 1.5)
            kill_icon.setPixmap(
                kill_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        kill_row.addWidget(kill_icon)
        kill_bar = QtWidgets.QProgressBar()
        kill_bar.setRange(0, max(1, max_kills))
        kill_bar.setValue(max(0, kills))
        kill_bar.setFormat(str(kills))
        kill_bar.setProperty("class", "kills")
        kill_row.addWidget(kill_bar, 1)
        vbox.addLayout(kill_row)

        if show_heals:
            heal_row = QtWidgets.QHBoxLayout()
            heal_icon = QtWidgets.QLabel()
            heal_path = os.path.join(
                os.path.dirname(__file__), "..", "Icons", "HealsICON.png"
            )
            heal_pix = QtGui.QPixmap(heal_path)
            if not heal_pix.isNull():
                size = int(QtGui.QFontMetrics(self.font()).height() * 1.5)
                heal_icon.setPixmap(
                    heal_pix.scaled(
                        size,
                        size,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )
            heal_row.addWidget(heal_icon)
            heal_bar = QtWidgets.QProgressBar()
            heal_bar.setRange(0, max(1, max_heals))
            heal_bar.setValue(max(0, heals))
            heal_bar.setFormat(str(heals))
            heal_bar.setProperty("class", "healed")
            heal_row.addWidget(heal_bar, 1)
            vbox.addLayout(heal_row)


class SkillStatsPopup(QtWidgets.QFrame):
    """Popup widget listing statistics for a hero's skills."""

    def __init__(
        self,
        skills: list[dict],
        max_kills: int,
        max_heals: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.ToolTip)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        for data in skills:
            widget = SkillStatWidget(
                data.get("name", ""),
                data.get("casts", 0),
                data.get("kills", 0),
                data.get("heals", 0),
                max_kills,
                max_heals,
                data.get("show_heals", True),
            )
            layout.addWidget(widget)


class PortraitLabel(QtWidgets.QLabel):
    """Hero portrait that shows a :class:`SkillStatsPopup` on hover."""

    def __init__(
        self,
        skills: list[dict],
        total_kills: int,
        total_heals: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._skills = skills
        self._total_kills = total_kills
        self._total_heals = total_heals
        self._popup: SkillStatsPopup | None = None

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:  # type: ignore[override]
        if self._skills:
            self._popup = SkillStatsPopup(
                self._skills, self._total_kills, self._total_heals, self
            )
            pos = self.mapToGlobal(self.rect().bottomLeft())
            self._popup.move(pos)
            self._popup.show()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
        if self._popup:
            self._popup.close()
            self._popup = None
        super().leaveEvent(event)


class HeroStatsHeader(QtWidgets.QWidget):
    """Header row that labels hero statistics columns."""

    def __init__(
        self, align_right: bool = False, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        load_styles()

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        portrait_spacer = QtWidgets.QWidget()
        portrait_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        name_spacer = QtWidgets.QWidget()

        if align_right:
            headers = [("Kills", 0), ("Heals", 1), ("Remaining Troops", 2)]
            layout.addWidget(name_spacer, 0, 3)
            layout.addWidget(portrait_spacer, 0, 4)
        else:
            headers = [("Remaining Troops", 2), ("Heals", 3), ("Kills", 4)]
            layout.addWidget(portrait_spacer, 0, 0)
            layout.addWidget(name_spacer, 0, 1)

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
            vbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

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
                container, 0, col, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
            )
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
        hero_skill_stats: list[list[dict]] | None = None,
        align_right: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_styles()

        self.setProperty("team", team_color.lower())
        self._total_kills = kills
        self._total_healed = healed
        self._hero_skill_stats = hero_skill_stats or []
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        portrait_container = QtWidgets.QWidget()
        portrait_layout = QtWidgets.QHBoxLayout(portrait_container)
        portrait_layout.setContentsMargins(0, 0, 0, 0)
        portrait_layout.setSpacing(0)

        self._portrait_labels: list[QtWidgets.QLabel] = []
        self._portrait_pixmaps: list[QtGui.QPixmap] = []
        hero_stats_seq = self._hero_skill_stats + [[]] * 2
        for idx, path in enumerate((portrait_path, portrait2_path)):
            stats = hero_stats_seq[idx] if idx < len(hero_stats_seq) else []
            lbl = PortraitLabel(stats, self._total_kills, self._total_healed)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            pix = QtGui.QPixmap(path)
            if pix.isNull():
                lbl.setText("No\nImage")
                lbl.setStyleSheet("background-color: #444; color: white;")
            else:
                self._portrait_pixmaps.append(pix)
                lbl.setPixmap(pix)
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


class ArenaStatsHeader(QtWidgets.QWidget):
    """Header for arena stats with two mirrored sides."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
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
                left.get("hero_skill_stats"),
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
                right.get("hero_skill_stats"),
                align_right=True,
            )
        else:
            right_widget = QtWidgets.QWidget()
        layout.addWidget(right_widget)

