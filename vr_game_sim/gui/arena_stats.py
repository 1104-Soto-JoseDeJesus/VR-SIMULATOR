from __future__ import annotations

import os

from vr_game_sim.metadata_loader import get_skill_description
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL

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

            # Compute totals across the entire army
            total_shielded = sum(
                s.get("shielded", 0)
                for skill_list in self._skills
                for s in (skill_list or [])
            )
            total_damage_reduced = sum(
                s.get("damage_reduced", 0)
                for skill_list in self._skills
                for s in (skill_list or [])
            )
            total_rage_reduced = sum(
                s.get("rage_reduced", 0)
                for skill_list in self._skills
                for s in (skill_list or [])
            )
            seen_ids: set[str] = set()
            total_rage = 0
            for skill_list in self._skills:
                for s in (skill_list or []):
                    sid = s.get("id")
                    if sid == "base_rage" and sid in seen_ids:
                        continue
                    if sid == "base_rage":
                        seen_ids.add(sid)
                    total_rage += s.get("rage", 0)

            dlg = HeroSkillDialog(
                hero_name,
                skills,
                self._total_kills,
                self._total_healed,
                total_shielded,
                total_rage_reduced,
                total_rage,
                total_damage_reduced,
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
        total_rage_reduced: int,
        total_rage: int,
        total_damage_reduced: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        raw_name = data.get("name", "")
        rarity = data.get("rarity")
        display_name = raw_name or ""
        if rarity and rarity not in display_name:
            display_name = f"{display_name} ({rarity})" if display_name else f"({rarity})"
        name_lbl = QtWidgets.QLabel(display_name)
        skill_id = data.get("id")
        tooltip_lines: list[str] = []
        skill_name_for_desc = raw_name or None
        if skill_id:
            desc = get_skill_description(skill_id, skill_name_for_desc)
            if desc:
                tooltip_lines.append(desc)
            elif isinstance(skill_id, str):
                skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id)
                fallback_name = (
                    skill_def.get("name")
                    if isinstance(skill_def, dict)
                    else skill_name_for_desc
                )
                if fallback_name and fallback_name != skill_name_for_desc:
                    desc = get_skill_description(skill_id, fallback_name)
                    if desc:
                        tooltip_lines.append(desc)
        if rarity:
            tooltip_lines.append(f"Rarity: {rarity}")
        if tooltip_lines:
            name_lbl.setToolTip("\n\n".join(tooltip_lines))
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

        colors = {
            "kills": ("#8B0000", "#FF9999"),
            "healed": ("#006400", "#90EE90"),
            "shielded": ("#00008B", "#ADD8E6"),
            "damage_reduced": ("#FF8C00", "#FFD580"),
            "rage_reduced": ("#FF1493", "#FFB6C1"),
            "rage": ("#4B0082", "#D8BFD8"),
        }

        def setup_bar(bar, total, direct, boost, deep, light, cls):
            bar.setRange(0, max(1, total))
            bar.setValue(direct + boost)
            bar.setFormat(str(direct + boost))
            bar.setProperty("class", cls)
            if boost > 0 and direct > 0:
                ratio = direct / (direct + boost)
                bar.setStyleSheet(
                    f"QProgressBar::chunk {{background: QLinearGradient(x1:0, y1:0, x2:1, y2:0, stop:0 {deep}, stop:{ratio:.3f} {deep}, stop:{ratio:.3f} {light}, stop:1 {light};}}"
                )
            elif boost > 0:
                bar.setStyleSheet(f"QProgressBar::chunk {{background-color: {light};}}")
            else:
                bar.setStyleSheet("")

        # Kills
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
        setup_bar(kills_bar, total_kills, data.get("kills", 0), data.get("boosted_kills", 0), *colors["kills"], "kills")
        layout.addWidget(kills_bar, 0, 4)

        # Heals
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
        setup_bar(heals_bar, total_healed, data.get("heals", 0), data.get("boosted_heals", 0), *colors["healed"], "healed")
        layout.addWidget(heals_bar, 0, 6)

        # Shields
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
        setup_bar(shield_bar, total_shielded, data.get("shielded", 0), data.get("boosted_shielded", 0), *colors["shielded"], "shielded")
        layout.addWidget(shield_bar, 0, 8)

        # Damage Reduction
        dr_icon = QtWidgets.QLabel()
        dr_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "DamageReduction.png"
        )
        dr_pix = QtGui.QPixmap(dr_path)
        if not dr_pix.isNull():
            dr_icon.setPixmap(
                dr_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(dr_icon, 0, 9)
        dr_bar = QtWidgets.QProgressBar()
        setup_bar(dr_bar, total_damage_reduced, data.get("damage_reduced", 0), data.get("boosted_damage_reduced", 0), *colors["damage_reduced"], "damage_reduced")
        layout.addWidget(dr_bar, 0, 10)

        # Rage Reduction
        rr_icon = QtWidgets.QLabel()
        rr_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "RageReduction.png"
        )
        rr_pix = QtGui.QPixmap(rr_path)
        if not rr_pix.isNull():
            rr_icon.setPixmap(
                rr_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(rr_icon, 0, 11)
        rr_bar = QtWidgets.QProgressBar()
        setup_bar(rr_bar, total_rage_reduced, data.get("rage_reduced", 0), data.get("boosted_rage_reduced", 0), *colors["rage_reduced"], "rage_reduced")
        layout.addWidget(rr_bar, 0, 12)

        # Rage
        rage_icon = QtWidgets.QLabel()
        rage_path = os.path.join(
            os.path.dirname(__file__), "..", "Icons", "Rage.png"
        )
        rage_pix = QtGui.QPixmap(rage_path)
        if not rage_pix.isNull():
            rage_icon.setPixmap(
                rage_pix.scaled(
                    size,
                    size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(rage_icon, 0, 13)
        rage_bar = QtWidgets.QProgressBar()
        setup_bar(rage_bar, total_rage, data.get("rage", 0), data.get("boosted_rage", 0), *colors["rage"], "rage")
        layout.addWidget(rage_bar, 0, 14)

        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(4, 3)
        layout.setColumnStretch(6, 3)
        layout.setColumnStretch(8, 3)
        layout.setColumnStretch(10, 3)
        layout.setColumnStretch(12, 3)
        layout.setColumnStretch(14, 3)


class HeroSkillDialog(QtWidgets.QDialog):
    """Dialog displaying skill performance for a hero."""

    def __init__(
        self,
        hero_name: str,
        skills: list[dict],
        total_kills: int,
        total_healed: int,
        total_shielded: int,
        total_rage_reduced: int,
        total_rage: int,
        total_damage_reduced: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_styles()
        self.setWindowTitle(f"{hero_name} Skill Breakdown")
        layout = QtWidgets.QVBoxLayout(self)
        for data in skills:
            layout.addWidget(
                SkillStatsRow(
                    data, total_kills, total_healed, total_shielded, total_rage_reduced, total_rage, total_damage_reduced
                )
            )
        self.setLayout(layout)

