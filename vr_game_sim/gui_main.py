"""PyQt6 based GUI for configuring and running battles."""

from __future__ import annotations

import os
from typing import Any
import threading

from PyQt6 import QtCore, QtGui, QtWidgets
import shutil
from PIL import Image, ImageQt
import numpy as np

from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder
from vr_game_sim.main import (
    create_armies_from_data,
    run_additional_simulations,
    save_setup_to_file,
    load_setup_from_file,
)
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL, SkillType


class HeroEditDialog(QtWidgets.QDialog):
    """Dialog to edit or create a hero configuration."""

    def __init__(self, hero_config: dict | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Hero")
        self.setModal(True)

        layout = QtWidgets.QFormLayout(self)

        self.name_edit = QtWidgets.QLineEdit(hero_config.get("hero_name_or_preset", "") if hero_config else "")
        layout.addRow("Hero Name:", self.name_edit)

        def _skill_options(skill_type: SkillType, include_none: bool = True):
            opts: list[tuple[str, str]] = []
            for sid, sdef in SKILL_REGISTRY_GLOBAL.items():
                if sdef["type"] == skill_type:
                    opts.append((sdef["name"], sid))
            opts.sort(key=lambda x: x[0])
            if include_none:
                opts.insert(0, ("None", ""))
            return opts

        self.talent_boxes: list[QtWidgets.QComboBox] = []
        self.base_boxes: list[QtWidgets.QComboBox] = []
        self.plugin_boxes: list[QtWidgets.QComboBox] = []

        talent_opts = _skill_options(SkillType.TALENT)
        base_opts = _skill_options(SkillType.BASE_SKILL)
        plugin_opts = _skill_options(SkillType.PLUGIN_SKILL)

        for i in range(3):
            box = QtWidgets.QComboBox()
            for name, sid in talent_opts:
                box.addItem(name, sid)
            if hero_config and i < len(hero_config.get("talent_ids", [])):
                sid = hero_config["talent_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.talent_boxes.append(box)
            layout.addRow(f"Talent {i+1}:", box)

        for i in range(2):
            box = QtWidgets.QComboBox()
            for name, sid in base_opts:
                box.addItem(name, sid)
            if hero_config and i < len(hero_config.get("base_skill_ids", [])):
                sid = hero_config["base_skill_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.base_boxes.append(box)
            layout.addRow(f"Base Skill {i+1}:", box)

        for i in range(2):
            box = QtWidgets.QComboBox()
            for name, sid in plugin_opts:
                box.addItem(name, sid)
            if hero_config and i < len(hero_config.get("plugin_skill_ids", [])):
                sid = hero_config["plugin_skill_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.plugin_boxes.append(box)
            layout.addRow(f"Plugin Skill {i+1}:", box)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def result_config(self) -> dict | None:
        if self.result() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        return {
            "hero_name_or_preset": self.name_edit.text().strip(),
            "talent_ids": [box.currentData() or "" for box in self.talent_boxes],
            "base_skill_ids": [box.currentData() or "" for box in self.base_boxes if box.currentText() != "None"],
            "plugin_skill_ids": [box.currentData() or "" for box in self.plugin_boxes if box.currentText() != "None"],
        }


class ArmyFrame(QtWidgets.QGroupBox):
    """Inputs for a single army."""

    def __init__(self, index: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(f"Army {index}", parent)
        self.index = index

        self.hero_options = ["None", "Custom"] + sorted(name.capitalize() for name in HERO_PRESETS.keys())

        self.name_edit = QtWidgets.QLineEdit(f"Army {index}")
        self.unit_combo = QtWidgets.QComboBox()
        for u in sorted(Unit.ALLOWED_TYPES):
            self.unit_combo.addItem(u)
        self.unit_combo.currentTextChanged.connect(self._unit_changed)
        self.tier_spin = QtWidgets.QSpinBox()
        self.tier_spin.setRange(min(Unit.ALLOWED_TIERS), max(Unit.ALLOWED_TIERS))
        self.tier_spin.setValue(5)

        self.count_spin = QtWidgets.QSpinBox()
        self.count_spin.setRange(0, 100000000)
        self.count_spin.setValue(100000)

        self.atk_edit = QtWidgets.QDoubleSpinBox()
        self.atk_edit.setRange(-10.0, 10.0)
        self.atk_edit.setSingleStep(0.1)
        self.atk_edit.setValue(0.0)

        self.def_edit = QtWidgets.QDoubleSpinBox()
        self.def_edit.setRange(-10.0, 10.0)
        self.def_edit.setSingleStep(0.1)
        self.def_edit.setValue(0.0)

        self.hp_edit = QtWidgets.QDoubleSpinBox()
        self.hp_edit.setRange(-10.0, 10.0)
        self.hp_edit.setSingleStep(0.1)
        self.hp_edit.setValue(0.0)

        self.unrevivable_spin = QtWidgets.QDoubleSpinBox()
        self.unrevivable_spin.setRange(0.0, 1.0)
        self.unrevivable_spin.setSingleStep(0.05)
        self.unrevivable_spin.setValue(0.5)

        self.hero1_combo = QtWidgets.QComboBox()
        self.hero2_combo = QtWidgets.QComboBox()
        for combo in [self.hero1_combo, self.hero2_combo]:
            for opt in self.hero_options:
                combo.addItem(opt)
        self.hero1_combo.currentTextChanged.connect(lambda n: self._hero_selected(1, n))
        self.hero2_combo.currentTextChanged.connect(lambda n: self._hero_selected(2, n))

        self.edit_btn1 = QtWidgets.QPushButton("Edit")
        self.edit_btn2 = QtWidgets.QPushButton("Edit")
        self.edit_btn1.clicked.connect(lambda: self.edit_hero(1))
        self.edit_btn2.clicked.connect(lambda: self.edit_hero(2))

        self.custom_heroes: dict[int, dict] = {1: None, 2: None}

        layout = QtWidgets.QGridLayout(self)
        row = 0
        layout.addWidget(QtWidgets.QLabel("Name:"), row, 0)
        layout.addWidget(self.name_edit, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Unit type:"), row, 0)
        layout.addWidget(self.unit_combo, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Tier:"), row, 0)
        layout.addWidget(self.tier_spin, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Troops:"), row, 0)
        layout.addWidget(self.count_spin, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Atk mod:"), row, 0)
        layout.addWidget(self.atk_edit, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Def mod:"), row, 0)
        layout.addWidget(self.def_edit, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("HP mod:"), row, 0)
        layout.addWidget(self.hp_edit, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Unrevivable ratio:"), row, 0)
        layout.addWidget(self.unrevivable_spin, row, 1)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Hero 1:"), row, 0)
        self.hero1_info = QtWidgets.QLabel()
        self.hero1_info.setWordWrap(True)
        layout.addWidget(self.hero1_combo, row, 1)
        layout.addWidget(self.edit_btn1, row, 2)
        layout.addWidget(self.hero1_info, row, 3)
        row += 1

        layout.addWidget(QtWidgets.QLabel("Hero 2:"), row, 0)
        self.hero2_info = QtWidgets.QLabel()
        self.hero2_info.setWordWrap(True)
        layout.addWidget(self.hero2_combo, row, 1)
        layout.addWidget(self.edit_btn2, row, 2)
        layout.addWidget(self.hero2_info, row, 3)
        # Extra row for preview content added externally

        # --- Troop type icon ---
        self.unit_icon = QtWidgets.QLabel()
        self.unit_icon.setFixedSize(92, 92)
        self.unit_icon.setScaledContents(True)

        # --- Hero 1 preview widget ---
        self.hero1_img = QtWidgets.QLabel()
        self.hero1_img.setFixedSize(64, 92)
        self.hero1_img.setScaledContents(True)
        self.hero1_plugin_imgs = [QtWidgets.QLabel(), QtWidgets.QLabel()]
        for lbl in self.hero1_plugin_imgs:
            lbl.setFixedSize(75, 92)
            lbl.setScaledContents(True)
        hero1_preview_layout = QtWidgets.QHBoxLayout()
        hero1_preview_layout.setContentsMargins(0, 0, 0, 0)
        hero1_preview_layout.setSpacing(30)
        if self.index == 1:
            hero1_preview_layout.addWidget(self.hero1_img)
            for lbl in self.hero1_plugin_imgs:
                hero1_preview_layout.addWidget(lbl)
        else:
            for lbl in reversed(self.hero1_plugin_imgs):
                hero1_preview_layout.addWidget(lbl)
            hero1_preview_layout.addWidget(self.hero1_img)
        hero1_preview_widget = QtWidgets.QWidget()
        hero1_preview_widget.setLayout(hero1_preview_layout)

        # --- Hero 2 preview widget ---
        self.hero2_img = QtWidgets.QLabel()
        self.hero2_img.setFixedSize(64, 92)
        self.hero2_img.setScaledContents(True)
        self.hero2_plugin_imgs = [QtWidgets.QLabel(), QtWidgets.QLabel()]
        for lbl in self.hero2_plugin_imgs:
            lbl.setFixedSize(75, 92)
            lbl.setScaledContents(True)
        hero2_preview_layout = QtWidgets.QHBoxLayout()
        hero2_preview_layout.setContentsMargins(0, 0, 0, 0)
        hero2_preview_layout.setSpacing(30)
        if self.index == 1:
            hero2_preview_layout.addWidget(self.hero2_img)
            for lbl in self.hero2_plugin_imgs:
                hero2_preview_layout.addWidget(lbl)
        else:
            for lbl in reversed(self.hero2_plugin_imgs):
                hero2_preview_layout.addWidget(lbl)
            hero2_preview_layout.addWidget(self.hero2_img)
        hero2_preview_widget = QtWidgets.QWidget()
        hero2_preview_widget.setLayout(hero2_preview_layout)

        # --- Combine troop icon with hero previews ---
        self.preview_widget = QtWidgets.QWidget()
        if self.index == 1:
            preview_layout = QtWidgets.QHBoxLayout(self.preview_widget)
        else:
            preview_layout = QtWidgets.QHBoxLayout(self.preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(30)

        heroes_layout = QtWidgets.QVBoxLayout()
        heroes_layout.setContentsMargins(0, 0, 0, 0)
        heroes_layout.setSpacing(30)
        heroes_layout.addWidget(hero1_preview_widget)
        heroes_layout.addWidget(hero2_preview_widget)
        heroes_widget = QtWidgets.QWidget()
        heroes_widget.setLayout(heroes_layout)

        if self.index == 1:
            preview_layout.addWidget(self.unit_icon)
            preview_layout.addWidget(heroes_widget)
        else:
            preview_layout.addWidget(heroes_widget)
            preview_layout.addWidget(self.unit_icon)

        self.unit_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Initialize info labels
        self._hero_selected(1, self.hero1_combo.currentText())
        self._hero_selected(2, self.hero2_combo.currentText())
        self._unit_changed(self.unit_combo.currentText())

    def _add_custom_option(self, name: str) -> None:
        if name not in self.hero_options:
            self.hero_options.append(name)
            self.hero1_combo.addItem(name)
            self.hero2_combo.addItem(name)

    def edit_hero(self, slot: int) -> None:
        current_cfg = self.custom_heroes.get(slot)
        if current_cfg is None:
            hero_name = self.hero1_combo.currentText() if slot == 1 else self.hero2_combo.currentText()
            preset = HERO_PRESETS.get(hero_name.lower())
            if preset:
                current_cfg = {
                    "hero_name_or_preset": hero_name,
                    "talent_ids": preset.get("talents", []),
                    "base_skill_ids": preset.get("base_skills", []),
                    "plugin_skill_ids": preset.get("plugin_skills", []),
                }

        dlg = HeroEditDialog(current_cfg, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dlg.result_config()
            if cfg:
                self.custom_heroes[slot] = cfg
                name = cfg["hero_name_or_preset"]
                self._add_custom_option(name)
                if slot == 1:
                    self.hero1_combo.setCurrentText(name)
                    self._hero_selected(1, name)
                else:
                    self.hero2_combo.setCurrentText(name)
                    self._hero_selected(2, name)

    def _hero_selected(self, slot: int, name: str) -> None:
        """Update preset info labels and reset custom config if preset changed."""
        if name in {"None", "Custom"}:
            info = ""
        else:
            preset = HERO_PRESETS.get(name.lower())
            if preset:
                talents = ", ".join(
                    SKILL_REGISTRY_GLOBAL.get(t, {}).get("name", t) for t in preset.get("talents", [])
                )
                bases = ", ".join(
                    SKILL_REGISTRY_GLOBAL.get(b, {}).get("name", b) for b in preset.get("base_skills", [])
                )
                info = f"Talents: {talents} | Base: {bases}"
            else:
                info = ""

        if slot == 1:
            self.hero1_info.setText(info)
        else:
            self.hero2_info.setText(info)

        cfg = self.custom_heroes.get(slot)
        if cfg and cfg.get("hero_name_or_preset") != name and name not in {"None", "Custom"}:
            self.custom_heroes[slot] = None

        img_label = self.hero1_img if slot == 1 else self.hero2_img
        img_label.clear()
        img_label.setToolTip(name if name not in {"None", "Custom"} else "")
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        for lbl in plugin_labels:
            lbl.clear()
            lbl.setToolTip("")
        if name not in {"None", "Custom"}:
            img_path = os.path.join(os.path.dirname(__file__), "Hero Images", f"{name.capitalize()}.png")
            if os.path.exists(img_path):
                pix = QtGui.QPixmap(img_path)
                img_label.setPixmap(
                    pix.scaled(64, 92, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                )
                img_label.setText("")
            else:
                img_label.setText(name)
                img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            plugin_ids: list[str] = []
            if cfg and cfg.get("hero_name_or_preset") == name:
                plugin_ids = cfg.get("plugin_skill_ids", [])
            else:
                preset = HERO_PRESETS.get(name.lower())
                if preset:
                    plugin_ids = preset.get("plugin_skills", [])
            for lbl, sid in zip(plugin_labels, plugin_ids):
                skill_def = SKILL_REGISTRY_GLOBAL.get(sid)
                if not skill_def:
                    continue
                img_name = skill_def["name"].replace("'", "").replace(" ", "-") + ".png"
                skill_img_path = os.path.join(os.path.dirname(__file__), "Plugin Skill Images", img_name)
                lbl.setToolTip(skill_def.get("name", sid))
                if os.path.exists(skill_img_path):
                    pix = QtGui.QPixmap(skill_img_path)
                    lbl.setPixmap(
                        pix.scaled(75, 92, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                    )
                    lbl.setText("")
                else:
                    lbl.setText(skill_def.get("name", sid))
                    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def _unit_changed(self, unit: str) -> None:
        """Update the troop type icon when unit selection changes."""
        icon_path = os.path.join(os.path.dirname(__file__), "Icons", f"{unit}.png")
        if os.path.exists(icon_path):
            pix = QtGui.QPixmap(icon_path)
            self.unit_icon.setPixmap(
                pix.scaled(
                    92,
                    92,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.unit_icon.setText("")
        else:
            self.unit_icon.clear()
            self.unit_icon.setText(unit)
            self.unit_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def populate_from_config(self, cfg: dict) -> None:
        self.name_edit.setText(cfg.get("army_name", f"Army {self.index}"))
        self.unit_combo.setCurrentText(cfg.get("unit_type", "pikemen"))
        self._unit_changed(self.unit_combo.currentText())
        self.tier_spin.setValue(int(cfg.get("tier", 5)))
        self.count_spin.setValue(int(cfg.get("count", 100000)))
        self.atk_edit.setValue(float(cfg.get("atk_mod", 0)))
        self.def_edit.setValue(float(cfg.get("def_mod", 0)))
        self.hp_edit.setValue(float(cfg.get("hp_mod", 0)))

        self.unrevivable_spin.setValue(float(cfg.get("unrevivable_ratio", 0.5)))

        hero_combos = [self.hero1_combo, self.hero2_combo]
        for idx, combo in enumerate(hero_combos, start=1):
            combo.setCurrentText("None")
            self.custom_heroes[idx] = None
        for idx, hero_cfg in enumerate(cfg.get("heroes", []), start=1):
            if idx > 2:
                break
            name = hero_cfg.get("hero_name_or_preset", "")
            preset = HERO_PRESETS.get(name.lower())
            if preset and preset.get("talents") == hero_cfg.get("talent_ids") and preset.get("base_skills") == hero_cfg.get("base_skill_ids") and preset.get("plugin_skills") == hero_cfg.get("plugin_skill_ids"):
                hero_name_display = name.capitalize()
            else:
                hero_name_display = name
                self.custom_heroes[idx] = hero_cfg
                self._add_custom_option(name)
            hero_combos[idx - 1].setCurrentText(hero_name_display)
            self._hero_selected(idx, hero_name_display)
        for idx, combo in enumerate(hero_combos, start=1):
            self._hero_selected(idx, combo.currentText())

    def build_config(self) -> dict:
        heroes_cfg = []
        for idx, combo in enumerate([self.hero1_combo, self.hero2_combo], start=1):
            hero_name = combo.currentText()
            if hero_name and hero_name not in {"None", "Custom"}:
                custom_cfg = self.custom_heroes.get(idx)
                if custom_cfg and custom_cfg.get("hero_name_or_preset") == hero_name:
                    heroes_cfg.append(custom_cfg)
                    continue
                preset = HERO_PRESETS.get(hero_name.lower())
                if preset:
                    heroes_cfg.append(
                        {
                            "hero_name_or_preset": hero_name,
                            "talent_ids": preset.get("talents", []),
                            "base_skill_ids": preset.get("base_skills", []),
                            "plugin_skill_ids": preset.get("plugin_skills", []),
                        }
                    )

        return {
            "army_name": self.name_edit.text() or f"Army {self.index}",
            "unit_type": self.unit_combo.currentText(),
            "tier": int(self.tier_spin.value()),
            "count": int(self.count_spin.value()),
            "atk_mod": float(self.atk_edit.value()),
            "def_mod": float(self.def_edit.value()),
            "hp_mod": float(self.hp_edit.value()),
            "unrevivable_ratio": float(self.unrevivable_spin.value()),
            "heroes": heroes_cfg,
        }


class SimulationWorker(QtCore.QThread):
    progress_update = QtCore.pyqtSignal(int, int)
    finished_text = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, setup_data: list[dict]) -> None:
        super().__init__()
        self.setup_data = setup_data

    def run(self) -> None:
        try:
            armies = create_armies_from_data(self.setup_data)
            report_builder = ReportBuilder(use_color=False)
            sim = GameSimulator(armies[0], armies[1], report_builder, track_stats=True)
            report_text = sim.simulate_battle()

            def progress_cb(done: int, total: int) -> None:
                self.progress_update.emit(done, total)

            win_rate = run_additional_simulations(
                self.setup_data,
                verbose=False,
                progress_callback=progress_cb,
                num_workers=os.cpu_count(),
            )

            result_text = (
                report_text
                + f"\nWin rate for {armies[0].name}: {win_rate*100:.1f}% over 300 runs.\n"
            )
            self.finished_text.emit(result_text)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self.error.emit(str(exc))


def display_histograms(
    scroll: QtWidgets.QScrollArea,
    army1_name: str = "Army 1",
    army2_name: str = "Army 2",
) -> None:
    """Render histogram images into the scroll area.

    A new widget is created each time to avoid layout re-parenting issues that
    previously caused crashes on some systems.  Images are scaled so that a
    2x2 grid fits within the available screen without clipping and the entire
    layout is centered within the scroll area."""

    old_widget = scroll.takeWidget()
    if old_widget is not None:
        old_widget.deleteLater()

    frame = QtWidgets.QWidget()
    # Allow the frame to resize with the scroll area so images are not clipped
    scroll.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    image_files = [
        "own_remaining_troops.png",
        "enemy_remaining_troops.png",
        "rounds_to_battle_end.png",
        "victory_distribution.png",
        "troop_difference.png",
        "diff_vs_rounds.png",
        "rounds_cdf.png",
        "rolling_stats.png",
        "damage_accumulated_army1.png",
        "damage_accumulated_army2.png",
        "heal_accumulated_army1.png",
        "heal_accumulated_army2.png",
        "shield_accumulated_army1.png",
        "shield_accumulated_army2.png",
        "rage_per_round_army1.png",
        "rage_per_round_army2.png",
    ]
    layout = QtWidgets.QGridLayout()
    layout.setSpacing(10)
    layout.setContentsMargins(10, 10, 10, 10)

    scroll_width = scroll.viewport().width()
    screen_geom = QtWidgets.QApplication.primaryScreen().availableGeometry()
    max_width = min(scroll_width - 40 if scroll_width > 40 else 300, screen_geom.width() // 2)
    max_height = screen_geom.height() // 2
    row = col = 0
    base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
    for img_name in image_files:
        path = os.path.join(base_hist_dir, img_name)
        if not os.path.exists(path):
            continue
        try:
            img = Image.open(path)
            if img.width > max_width or img.height > max_height:
                ratio = min(max_width / img.width, max_height / img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
            qimg = ImageQt.ImageQt(img)
            pix = QtGui.QPixmap.fromImage(qimg)
        except Exception:
            continue
        lbl = QtWidgets.QLabel()
        lbl.setPixmap(pix)
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "QLabel {"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "background-color: rgba(0, 0, 0, 80);"
            "color: #ffffff;"
            "}"
        )
        layout.addWidget(lbl, row, col, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        if img_name == "own_remaining_troops.png":
            caption_text = f"{army1_name} troops remaining"
        elif img_name == "enemy_remaining_troops.png":
            caption_text = f"{army2_name} troops remaining"
        elif img_name == "damage_accumulated_army1.png":
            caption_text = f"{army1_name} damage dealt (cumulative)"
        elif img_name == "damage_accumulated_army2.png":
            caption_text = f"{army2_name} damage dealt (cumulative)"
        elif img_name == "heal_accumulated_army1.png":
            caption_text = f"{army1_name} healing received (cumulative)"
        elif img_name == "heal_accumulated_army2.png":
            caption_text = f"{army2_name} healing received (cumulative)"
        elif img_name == "shield_accumulated_army1.png":
            caption_text = f"{army1_name} shields gained (cumulative)"
        elif img_name == "shield_accumulated_army2.png":
            caption_text = f"{army2_name} shields gained (cumulative)"
        elif img_name == "rage_per_round_army1.png":
            caption_text = f"{army1_name} rage per round"
        elif img_name == "rage_per_round_army2.png":
            caption_text = f"{army2_name} rage per round"
        else:
            caption_text = img_name.replace("_", " ").replace(".png", "").title()
        caption = QtWidgets.QLabel(caption_text)
        caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet(
            "QLabel { color: #dddddd; background-color: transparent; }"
        )
        layout.addWidget(caption, row + 1, col)
        col += 1
        if col >= 2:
            col = 0
            row += 2

    outer = QtWidgets.QVBoxLayout()
    outer.addStretch()
    outer.addLayout(layout)
    outer.addStretch()
    outer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    frame.setLayout(outer)
    scroll.setWidget(frame)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Battle Simulator")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)

        # Remember the directory last used when loading/saving setups
        self.last_setup_dir = os.path.join(os.path.dirname(__file__), "setups")

        # --- Army Setup tab ---
        setup_tab = QtWidgets.QWidget()
        setup_layout = QtWidgets.QVBoxLayout(setup_tab)

        armies_row = QtWidgets.QHBoxLayout()
        self.army1_frame = ArmyFrame(1)
        self.army2_frame = ArmyFrame(2)
        armies_row.addWidget(self.army1_frame)
        armies_row.addWidget(self.army2_frame)
        setup_layout.addLayout(armies_row)

        preview_group = QtWidgets.QGroupBox("Army Preview")
        preview_layout = QtWidgets.QHBoxLayout(preview_group)
        preview_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_layout.setSpacing(30)

        vs_path = os.path.join(os.path.dirname(__file__), "Icons", "VS.png")
        self.vs_label = QtWidgets.QLabel()
        self.vs_label.setFixedSize(123, 110)
        self.vs_label.setScaledContents(True)
        if os.path.exists(vs_path):
            vs_pix = QtGui.QPixmap(vs_path)
            self.vs_label.setPixmap(
                vs_pix.scaled(
                    123,
                    110,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )

        preview_layout.addWidget(self.army1_frame.preview_widget)
        preview_layout.addWidget(self.vs_label)
        preview_layout.addWidget(self.army2_frame.preview_widget)

        setup_layout.addWidget(preview_group)

        self.tabs.addTab(setup_tab, "Army Setup")

        # --- Report tab ---
        self.output = QtWidgets.QTextEdit()
        self.output.setReadOnly(True)
        fixed_font = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        )
        self.output.setFont(fixed_font)
        self.output.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.tabs.addTab(self.output, "Report")

        # --- Figures tab ---
        self.hist_container = QtWidgets.QWidget()
        self.hist_scroll = QtWidgets.QScrollArea()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setWidget(self.hist_container)
        self.tabs.addTab(self.hist_scroll, "Figures")

        self.status = QtWidgets.QLabel("Ready")
        main_layout.addWidget(self.status)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        main_layout.addWidget(self.progress)

        btn_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(btn_layout)
        self.run_btn = QtWidgets.QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self.run_simulation)
        btn_layout.addWidget(self.run_btn)

        save_btn = QtWidgets.QPushButton("Save Setup")
        save_btn.clicked.connect(self.save_setup)
        btn_layout.addWidget(save_btn)

        load_btn = QtWidgets.QPushButton("Load Setup")
        load_btn.clicked.connect(self.load_setup)
        btn_layout.addWidget(load_btn)

        clear_btn = QtWidgets.QPushButton("Clear Output")
        clear_btn.clicked.connect(lambda: self.output.clear())
        btn_layout.addWidget(clear_btn)

        export_btn = QtWidgets.QPushButton("Export Figures")
        export_btn.clicked.connect(self.export_figures)
        btn_layout.addWidget(export_btn)

        summary_btn = QtWidgets.QPushButton("Export Summary Image")
        summary_btn.clicked.connect(self.export_summary_image)
        btn_layout.addWidget(summary_btn)

    # --- Setup load/save -------------------------------------------------
    def save_setup(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Setup",
            self.last_setup_dir,
            "JSON Files (*.json)",
        )
        if file_path:
            self.last_setup_dir = os.path.dirname(file_path)
            save_setup_to_file(
                [self.army1_frame.build_config(), self.army2_frame.build_config()],
                os.path.basename(file_path),
            )
            self.status.setText(f"Saved to {os.path.basename(file_path)}")

    def load_setup(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Setup",
            self.last_setup_dir,
            "JSON Files (*.json)",
        )
        if file_path:
            self.last_setup_dir = os.path.dirname(file_path)
            data = load_setup_from_file(file_path)
            if data and len(data) >= 2:
                self.army1_frame.populate_from_config(data[0])
                self.army2_frame.populate_from_config(data[1])
                self.status.setText(f"Loaded {os.path.basename(file_path)}")

    def export_figures(self) -> None:
        image_files = [
            "own_remaining_troops.png",
            "enemy_remaining_troops.png",
            "rounds_to_battle_end.png",
            "victory_distribution.png",
            "troop_difference.png",
            "diff_vs_rounds.png",
            "rounds_cdf.png",
            "rolling_stats.png",
            "damage_accumulated_army1.png",
            "damage_accumulated_army2.png",
            "heal_accumulated_army1.png",
            "heal_accumulated_army2.png",
            "shield_accumulated_army1.png",
            "shield_accumulated_army2.png",
            "rage_per_round_army1.png",
            "rage_per_round_army2.png",
        ]
        base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
        if not any(os.path.exists(os.path.join(base_hist_dir, f)) for f in image_files):
            QtWidgets.QMessageBox.warning(
                self, "No Figures", "No histogram images found. Run a simulation first."
            )
            return
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Export Figures", self.last_setup_dir
        )
        if dest_dir:
            for fname in image_files:
                src = os.path.join(base_hist_dir, fname)
                if os.path.exists(src):
                    try:
                        shutil.copy(src, os.path.join(dest_dir, fname))
                    except OSError as exc:
                        QtWidgets.QMessageBox.critical(
                            self, "Error", f"Failed to export {fname}: {exc}"
                        )
                        return
            QtWidgets.QMessageBox.information(
                self, "Export Complete", f"Figures exported to {dest_dir}"
            )

    def export_summary_image(self) -> None:
        """Combine preview and histogram images into a single PNG."""
        def make_transparent(
            pix: QtGui.QPixmap, bg_color: QtGui.QColor | None = None
        ) -> QtGui.QPixmap:
            """Return ``pix`` with background pixels made fully transparent.

            ``QPixmap.createMaskFromColor`` was previously used to strip the
            ``#353535`` background from histogram images and army previews. That
            approach converts the mask to 1-bit alpha and ended up stripping away
            most of the figure detail, leaving the exported summary image almost
            invisible.  Instead we now manually inspect each pixel and clear the
            alpha channel when its colour matches the background (within a small
            tolerance).  Existing transparency in the source pixmap is preserved.

            If ``bg_color`` is ``None`` the colour of the top-left pixel is used
            as the background.  This allows previews and histograms with different
            solid backgrounds to be made transparent without hard-coding the
            expected colour.
            """

            # ``QImage.Format_ARGB32`` was renamed in PyQt6 to live under the
            # ``QImage.Format`` enum.  Using the old attribute causes an
            # ``AttributeError`` and crashes the application when exporting the
            # summary image.  Resolve this by referencing the PyQt6 enum member
            # correctly.
            image = pix.toImage().convertToFormat(
                QtGui.QImage.Format.Format_ARGB32
            )
            ptr = image.bits()
            ptr.setsize(image.width() * image.height() * 4)
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                image.height(), image.width(), 4
            )
            if bg_color is None:
                bg_color = arr[0, 0, :3].copy()
            else:
                bg_color = np.array(
                    [bg_color.red(), bg_color.green(), bg_color.blue()],
                    dtype=np.uint8,
                )
            rgb = arr[:, :, :3].astype(np.int16)
            diff = np.abs(rgb - bg_color.astype(np.int16))
            mask = (diff <= 2).all(axis=-1)
            arr[mask, 3] = 0
            return QtGui.QPixmap.fromImage(image)

        image_files = [
            "own_remaining_troops.png",
            "enemy_remaining_troops.png",
            "rounds_to_battle_end.png",
            "victory_distribution.png",
        ]
        base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
        hist_pixmaps = []
        for fname in image_files:
            path = os.path.join(base_hist_dir, fname)
            if os.path.exists(path):
                pm = QtGui.QPixmap(path)
                pm = make_transparent(pm)
                hist_pixmaps.append(pm)
        if not hist_pixmaps:
            QtWidgets.QMessageBox.warning(
                self, "No Figures", "No histogram images found. Run a simulation first."
            )
            return

        # Capture army previews and vs image
        scale = 5
        p1 = self.army1_frame.preview_widget.grab().scaled(
            self.army1_frame.preview_widget.width() * scale,
            self.army1_frame.preview_widget.height() * scale,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        p1 = make_transparent(p1)
        p2 = self.army2_frame.preview_widget.grab().scaled(
            self.army2_frame.preview_widget.width() * scale,
            self.army2_frame.preview_widget.height() * scale,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        p2 = make_transparent(p2)
        vs_pix = self.vs_label.pixmap()
        if vs_pix is not None and not vs_pix.isNull():
            vs_pix = vs_pix.scaled(
                vs_pix.width() * scale,
                vs_pix.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            vs_pix = make_transparent(vs_pix)
            preview_parts = [p1, vs_pix, p2]
        else:
            preview_parts = [p1, p2]

        if len(preview_parts) == 3:
            # When the VS icon is present ensure it is centered horizontally.
            padding = vs_pix.width() // 2
            # Introduce a slightly larger padding between the VS icon and the
            # second army preview to make the spacing appear more balanced in
            # the exported summary image.
            extra_after_vs = 300

            # Calculate width so the VS icon sits exactly in the middle of the
            # preview image. This may introduce extra blank space on the shorter
            # side, but ensures the icon is horizontally centered in the final
            # summary.
            left_space = p1.width() + padding
            right_space = p2.width() + padding + extra_after_vs
            half_width = max(left_space, right_space)
            preview_width = vs_pix.width() + 2 * half_width
            preview_height = max(p.height() for p in preview_parts)
            preview_pix = QtGui.QPixmap(preview_width, preview_height)
            preview_pix.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(preview_pix)

            # Position the VS icon in the horizontal centre
            vs_x = (preview_width - vs_pix.width()) // 2
            vs_y = (preview_height - vs_pix.height()) // 2
            painter.drawPixmap(vs_x, vs_y, vs_pix)

            # Draw the army previews relative to the centred VS icon
            left_x = vs_x - padding - p1.width()
            y = (preview_height - p1.height()) // 2
            painter.drawPixmap(left_x, y, p1)

            right_x = vs_x + vs_pix.width() + padding + extra_after_vs
            y = (preview_height - p2.height()) // 2
            painter.drawPixmap(right_x, y, p2)

            painter.end()
        else:
            # No VS icon, fall back to simple side-by-side arrangement.
            padding = 30
            preview_width = p1.width() + p2.width() + padding
            preview_height = max(p1.height(), p2.height())
            preview_pix = QtGui.QPixmap(preview_width, preview_height)
            preview_pix.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(preview_pix)
            x = 0
            for idx, part in enumerate(preview_parts):
                y = (preview_height - part.height()) // 2
                painter.drawPixmap(x, y, part)
                x += part.width()
                if idx != len(preview_parts) - 1:
                    x += padding
            painter.end()

        final_width = max(preview_pix.width(), *(p.width() for p in hist_pixmaps))
        final_height = preview_pix.height() + sum(p.height() for p in hist_pixmaps)
        final_pix = QtGui.QPixmap(final_width, final_height)

        painter = QtGui.QPainter(final_pix)
        gradient = QtGui.QLinearGradient(0, 0, 0, final_height)
        gradient.setColorAt(0, QtGui.QColor("#4a4a4a"))
        gradient.setColorAt(1, QtGui.QColor("#1e1e1e"))
        painter.fillRect(final_pix.rect(), gradient)

        x = (final_width - preview_pix.width()) // 2
        painter.drawPixmap(x, 0, preview_pix)
        y = preview_pix.height()
        for p in hist_pixmaps:
            x = (final_width - p.width()) // 2
            painter.drawPixmap(x, y, p)
            y += p.height()
        painter.end()

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Summary Image",
            self.last_setup_dir,
            "PNG Files (*.png)"
        )
        if save_path:
            final_pix.save(save_path, "PNG")

    # --- Simulation handling --------------------------------------------
    def run_simulation(self) -> None:
        setup_data = [self.army1_frame.build_config(), self.army2_frame.build_config()]
        self.status.setText("Running simulation...")
        self.progress.setRange(0, 300)
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.worker = SimulationWorker(setup_data)
        self.worker.progress_update.connect(lambda d, t: (self.progress.setMaximum(t), self.progress.setValue(d)))
        self.worker.finished_text.connect(self._sim_finished)
        self.worker.error.connect(self._sim_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _sim_finished(self, text: str) -> None:
        self.output.setPlainText(text)
        display_histograms(
            self.hist_scroll,
            self.army1_frame.name_edit.text() or f"Army 1",
            self.army2_frame.name_edit.text() or f"Army 2",
        )
        self.progress.setValue(0)
        self.status.setText("Ready")
        self.run_btn.setEnabled(True)

    def _sim_error(self, msg: str) -> None:  # pragma: no cover - GUI feedback
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.progress.setValue(0)
        self.status.setText("Ready")
        self.run_btn.setEnabled(True)


def main() -> None:
    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #4a4a4a, stop:1 #1e1e1e);
        }
        """
    )
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()

