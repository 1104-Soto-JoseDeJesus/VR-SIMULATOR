from __future__ import annotations

import os
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.unit_definition import Unit
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL

from .hero_edit_dialog import HeroEditDialog


class ArmyFrame(QtWidgets.QGroupBox):
    """Inputs for a single army."""

    def __init__(self, index: int, parent: Optional[QtWidgets.QWidget] = None) -> None:
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

        layout.addWidget(QtWidgets.QLabel("Heavily Wounded Ratio:"), row, 0)
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

