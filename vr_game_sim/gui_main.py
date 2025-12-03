"""PyQt6 based GUI for configuring and running battles."""

from __future__ import annotations

import os
import random
import copy
from typing import Any, Callable, Iterable
import threading
import math
import json
import html
from functools import partial
import time
import re
import concurrent.futures
import base64
import mimetypes
import difflib
import io

from PyQt6 import QtCore, QtGui, QtWidgets
import shutil
from PIL import Image, ImageQt, ImageDraw
import numpy as np
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army, normalize_gem_skill_id
from vr_game_sim.gear_definitions import (
    GEAR_REGISTRY,
    GEAR_SLOT_ORDER,
    RARITY_BACKGROUNDS,
    normalize_gear_slot,
    resolve_gear,
)
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.main import (
    create_armies_from_data,
    run_additional_simulations,
    save_setup_to_file,
    load_setup_from_file,
    save_army_to_file,
    load_army_from_file,
    HISTOGRAM_BG_COLOR,
    SeedTarget,
)
from vr_game_sim import dynamic_unrevivable_config, troop_scalar_config
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL, SkillType
from vr_game_sim.enums import StatType
from vr_game_sim.metadata_loader import get_skill_description
from vr_game_sim.battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.navmesh import NavMesh
from itertools import zip_longest

from vr_game_sim.gui.arena_stats import ArenaStatsHeader, ArenaStatsRow
from vr_game_sim.skill_override_utils import diff_structures


BONUS_TROOP_TYPES = ("pikemen", "archers", "infantry")
BONUS_STATS_TEMPLATE = {
    "damage_reduction": {
        "all": 0.0,
        **{f"vs_{t}": 0.0 for t in BONUS_TROOP_TYPES},
        "reactive": 0.0,
        "cooperation": 0.0,
        "command": 0.0,
    },
    "damage_boost": {
        "all": 0.0,
        **{f"vs_{t}": 0.0 for t in BONUS_TROOP_TYPES},
        "reactive_crit_rate": 0.0,
        "cooperation_crit_rate": 0.0,
        "command_crit_rate": 0.0,
    },
    "shield_gain": 0.0,
    "burn_boost": 0.0,
    "poison_boost": 0.0,
    "lacerate_boost": 0.0,
    "basic_boost": 0.0,
    "counter_boost": 0.0,
    "reactive_skill_boost": 0.0,
    "rage_skill_boost": 0.0,
    "cooperation_skill_boost": 0.0,
    "command_skill_boost": 0.0,
}

JEWEL_SLOTS: list[tuple[str, str]] = [
    ("friggs_agate", "Frigg's Agate"),
    ("tyrs_emerald", "Tyr's Emerald"),
    ("thors_ruby", "Thor's Ruby"),
    ("freyas_amethyst", "Freya's Amethyst"),
    ("odins_amber", "Odin's Amber"),
    ("heimdalls_sapphire", "Heimdall's Sapphire"),
]

# Map each jewel slot to the hero index the jewel is socketed for.  The first
# hero receives the first three jewels, while the second hero receives the
# remaining three.  ``GEM_SLOT_HERO_INDEX`` mirrors the same structure to keep
# backwards compatibility with older configuration terminology.
JEWEL_SLOT_HERO_INDEX: dict[str, int] = {
    "friggs_agate": 0,
    "tyrs_emerald": 0,
    "thors_ruby": 0,
    "freyas_amethyst": 1,
    "odins_amber": 1,
    "heimdalls_sapphire": 1,
}

# Backwards compatibility for older saved configurations referencing gem slots.
GEM_SLOTS = JEWEL_SLOTS
GEM_SLOT_HERO_INDEX = JEWEL_SLOT_HERO_INDEX

_RARITY_SORT_ORDER = {"Legendary": 0, "Epic": 1, "Rare": 2, None: 99}


def default_bonus_stats() -> dict[str, Any]:
    """Return a fresh bonus stats dictionary with all values zeroed."""

    return copy.deepcopy(BONUS_STATS_TEMPLATE)


def merge_bonus_stats(
    base: dict[str, Any], overrides: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge ``overrides`` into ``base`` without modifying the inputs."""

    result = copy.deepcopy(base)
    if not overrides:
        return result
    for key, value in overrides.items():
        if key not in result:
            continue
        if isinstance(result[key], dict) and isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if sub_key in result[key]:
                    result[key][sub_key] = float(sub_val)
        elif not isinstance(result[key], dict):
            result[key] = float(value)
    return result


def serialize_bonus_stats(stats: dict[str, Any]) -> dict[str, Any]:
    """Return ``stats`` with zero entries removed for persistence."""

    serialized: dict[str, Any] = {}
    for key, value in stats.items():
        if isinstance(value, dict):
            nested = {
                sub_key: round(float(sub_val), 6)
                for sub_key, sub_val in value.items()
                if abs(float(sub_val)) > 1e-9
            }
            if nested:
                serialized[key] = nested
        else:
            val = float(value)
            if abs(val) > 1e-9:
                serialized[key] = round(val, 6)
    return serialized


def _sanitize_filename_component(name: str, fallback: str) -> str:
    """Return a filesystem-friendly representation of ``name``."""

    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (name or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned or fallback


def _should_skip_skill_trigger(
    clean_skill_name: str, clean_effect_text: str
) -> bool:
    """Return True if a skill trigger should be hidden from HTML output."""

    normalized_name = (clean_skill_name or "").strip()
    if normalized_name in {
        "Damage Commitment",
        "Dynamic Unrevivable",
        "Heal Commitment",
        "Healing Commitment",
    }:
        return True
    normalized_effect = (clean_effect_text or "").strip().lower()
    if normalized_effect:
        if re.search(r"\bcommit\w*\b", normalized_effect) and (
            "damage" in normalized_effect or "healing" in normalized_effect
        ):
            return True
    return False


def _default_export_basename(army1: str, army2: str, timestamp: float | None = None) -> str:
    """Return the default basename for exports using army names and date."""

    ts = timestamp if timestamp is not None else time.time()
    date_part = time.strftime("%Y-%m-%d", time.localtime(ts))
    first = _sanitize_filename_component(army1, "Army1")
    second = _sanitize_filename_component(army2, "Army2")
    return f"{first}_{second}_{date_part}"


def iter_bonus_stat_entries(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Return structured, non-zero bonus stat entries with formatting hints."""

    entries: list[dict[str, Any]] = []

    def add(label: str, value: float, invert: bool = False) -> None:
        if abs(value) <= 1e-9:
            return
        entries.append({"label": label, "value": float(value), "invert": invert})

    dr = stats.get("damage_reduction", {}) if isinstance(stats, dict) else {}
    add("Damage Reduction", float(dr.get("all", 0.0)), True)
    for troop in BONUS_TROOP_TYPES:
        add(
            f"Damage Reduction vs {troop.title()}",
            float(dr.get(f"vs_{troop}", 0.0)),
            True,
        )
    add(
        "Damage Reduction vs Reactive Skills",
        float(dr.get("reactive", 0.0)),
        True,
    )
    add(
        "Damage Reduction vs Cooperation Skills",
        float(dr.get("cooperation", 0.0)),
        True,
    )
    add(
        "Damage Reduction vs Command Skills",
        float(dr.get("command", 0.0)),
        True,
    )

    db = stats.get("damage_boost", {}) if isinstance(stats, dict) else {}
    add("Damage Boost", float(db.get("all", 0.0)))
    for troop in BONUS_TROOP_TYPES:
        add(
            f"Damage Boost vs {troop.title()}",
            float(db.get(f"vs_{troop}", 0.0)),
        )
    add(
        "Reactive Skill Critical Rate",
        float(db.get("reactive_crit_rate", 0.0)),
    )
    add(
        "Cooperation Skill Critical Rate",
        float(db.get("cooperation_crit_rate", 0.0)),
    )
    add(
        "Command Skill Critical Rate",
        float(db.get("command_crit_rate", 0.0)),
    )

    add("Shield Gain Boost", float(stats.get("shield_gain", 0.0)))
    add("Burn Boost", float(stats.get("burn_boost", 0.0)))
    add("Poison Boost", float(stats.get("poison_boost", 0.0)))
    add("Lacerate Boost", float(stats.get("lacerate_boost", 0.0)))
    add("Basic Attack Boost", float(stats.get("basic_boost", 0.0)))
    add("Counterattack Boost", float(stats.get("counter_boost", 0.0)))
    add(
        "Reactive Skill Damage Boost",
        float(stats.get("reactive_skill_boost", 0.0)),
    )
    add("Rage Skill Damage Boost", float(stats.get("rage_skill_boost", 0.0)))
    add(
        "Cooperation Skill Damage Boost",
        float(stats.get("cooperation_skill_boost", 0.0)),
    )
    add(
        "Command Skill Damage Boost",
        float(stats.get("command_skill_boost", 0.0)),
    )

    return entries


def iter_skill_bonus_entries_from_effects(
    effects: Iterable[Any],
) -> list[dict[str, Any]]:
    """Return structured bonus entries for always-on skill effects."""

    label_map: dict[StatType, tuple[str, bool]] = {
        StatType.REACTIVE_SKILL_CRIT_RATE: ("Reactive Skill Critical Rate", False),
        StatType.COOPERATION_SKILL_CRIT_RATE: ("Cooperation Skill Critical Rate", False),
        StatType.COMMAND_SKILL_CRIT_RATE: ("Command Skill Critical Rate", False),
    }

    entries: list[dict[str, Any]] = []
    for effect in effects or []:
        config = getattr(effect, "config", None) or {}
        if not config.get("manual_bonus_stat"):
            continue
        source_skill = getattr(effect, "source_skill_id", "") or ""
        if (
            source_skill == "manual_bonus_stats"
            or str(source_skill).startswith("gear::")
        ):
            continue
        stat = config.get("stat_to_mod")
        label_info = label_map.get(stat)
        if not label_info:
            continue
        label, invert = label_info
        try:
            magnitude = float(getattr(effect, "magnitude", 0.0))
        except (TypeError, ValueError):
            continue
        entries.append({"label": label, "value": magnitude, "invert": invert})
    return entries


def get_pdf_layout_path() -> str:
    """Return path for persisted PDF layout configuration."""
    return os.path.join(os.path.dirname(__file__), "pdf_layout.json")


def gem_skill_options_for_slot(slot_key: str) -> list[tuple[str, str]]:
    """Return ``(label, skill_id)`` pairs for the given jewel slot."""

    options: list[tuple[str, str]] = [("None", "")]
    entries: list[tuple[int, int, str, str]] = []
    for skill_id, skill_def in SKILL_REGISTRY_GLOBAL.items():
        if skill_def.get("type") != SkillType.GEM_SKILL:
            continue
        cfg = skill_def.get("config", {}) or {}
        if cfg.get("gem_slot") != slot_key:
            continue
        rarity = cfg.get("rarity")
        sort_key = _RARITY_SORT_ORDER.get(rarity, 99)
        ui_order = int(cfg.get("ui_order", 0))
        name = skill_def.get("name", skill_id)
        entries.append((sort_key, ui_order, name, skill_id))
    entries.sort(key=lambda item: (item[0], item[1], item[2]))
    options.extend((name, sid) for _, _, name, sid in entries)
    return options


def load_pdf_layout() -> list[dict]:
    """Load PDF layout from disk, returning default if missing or invalid."""
    path = get_pdf_layout_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        pages = data.get("pages")
        if isinstance(pages, list):
            result: list[dict] = []
            for page in pages:
                if not isinstance(page, dict):
                    continue
                items = []
                for item in page.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    x = item.get("x")
                    y = item.get("y")
                    if not isinstance(itype, str) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                        continue
                    entry = {"type": itype, "x": float(x), "y": float(y)}
                    scale = item.get("scale")
                    if isinstance(scale, (int, float)):
                        entry["scale"] = float(scale)
                    items.append(entry)
                result.append({"items": items})
            if result:
                return result
    except (OSError, json.JSONDecodeError):
        pass
    return [{"items": []}]


def save_pdf_layout(pages: list[dict]) -> None:
    """Persist PDF layout configuration to disk."""
    path = get_pdf_layout_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"pages": pages}, fh, indent=2)
    except OSError:
        pass


def make_transparent(
    pix: QtGui.QPixmap, bg_color: QtGui.QColor | None = None
) -> QtGui.QPixmap:
    """Return ``pix`` with background pixels made fully transparent.

    ``QPixmap.createMaskFromColor`` was previously used to strip the
    ``#353535`` background from histogram images and army previews. That
    approach converts the mask to 1-bit alpha and removed most detail.  This
    helper instead inspects each pixel and clears the alpha channel when its
    colour matches the background (within a small tolerance). Existing
    transparency in the source pixmap is preserved.

    If ``bg_color`` is ``None`` the colour of the top-left pixel is used as the
    background, allowing different solid backgrounds to be handled without
    hard-coding the expected colour.
    """

    fmt_obj = getattr(QtGui.QImage, "Format", None)
    if fmt_obj is not None and hasattr(fmt_obj, "Format_ARGB32"):
        fmt = fmt_obj.Format_ARGB32
    else:
        fmt = QtGui.QImage.Format_ARGB32
    if pix.isNull():
        return pix
    image = pix.toImage().convertToFormat(fmt)
    # Guard against invalid or empty pixmaps which would otherwise cause
    # indexing errors when accessing pixel data. Returning the original pixmap
    # preserves previous behaviour without crashing the application.
    if image.width() == 0 or image.height() == 0:
        return pix
    ptr = image.bits()
    ptr.setsize(image.width() * image.height() * 4)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(image.height(), image.width(), 4)
    if bg_color is None:
        bg_color = arr[0, 0, :3].copy()
    else:
        bg_color = np.array(
            [bg_color.red(), bg_color.green(), bg_color.blue()], dtype=np.uint8
        )
    rgb = arr[:, :, :3].astype(np.int16)
    diff = np.abs(rgb - bg_color.astype(np.int16))
    mask = (diff <= 2).all(axis=-1)
    arr[mask, 3] = 0
    return QtGui.QPixmap.fromImage(image)


class ThousandSepSpinBox(QtWidgets.QSpinBox):
    """QSpinBox that displays numbers with thousand separators."""

    def textFromValue(self, value: int) -> str:  # type: ignore[override]
        return f"{value:,}"

    def valueFromText(self, text: str) -> int:  # type: ignore[override]
        clean = text.replace(",", "")
        try:
            return int(clean)
        except ValueError:
            return 0


class SeedOutcomeDialog(QtWidgets.QDialog):
    """Dialog that lets the user choose a preferred replay outcome."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        army1_name: str,
        army2_name: str,
        current: SeedTarget | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Seed Outcome")
        current_data: SeedTarget = dict(current) if current else {}
        self._target: SeedTarget | None = current_data or None

        layout = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            "Choose which battle outcome should be replayed when running a batch."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.button_group = QtWidgets.QButtonGroup(self)
        self.army1_radio = QtWidgets.QRadioButton(army1_name or "Army 1")
        self.army2_radio = QtWidgets.QRadioButton(army2_name or "Army 2")
        self.button_group.addButton(self.army1_radio, 1)
        self.button_group.addButton(self.army2_radio, 2)

        radio_layout = QtWidgets.QHBoxLayout()
        radio_layout.addWidget(self.army1_radio)
        radio_layout.addWidget(self.army2_radio)
        layout.addLayout(radio_layout)

        self.remaining_spin = ThousandSepSpinBox(self)
        self.remaining_spin.setRange(0, 2_000_000)
        self.remaining_spin.setSingleStep(1_000)
        remaining_default = current_data.get("remaining")
        self.remaining_spin.setValue(
            int(remaining_default) if isinstance(remaining_default, (int, float)) else 50_000
        )

        form = QtWidgets.QFormLayout()
        form.addRow("Remaining troops:", self.remaining_spin)

        self.round_checkbox = QtWidgets.QCheckBox("Match rounds")
        form.addRow(self.round_checkbox)

        self.rounds_spin = QtWidgets.QSpinBox(self)
        self.rounds_spin.setRange(1, 10_000)
        rounds_default = current_data.get("rounds")
        self.rounds_spin.setValue(
            int(rounds_default) if isinstance(rounds_default, (int, float)) else 100
        )
        form.addRow("Target rounds:", self.rounds_spin)

        self.round_tolerance_spin = QtWidgets.QSpinBox(self)
        self.round_tolerance_spin.setRange(0, 10_000)
        tolerance_default = current_data.get("round_tolerance")
        self.round_tolerance_spin.setValue(
            int(tolerance_default) if isinstance(tolerance_default, (int, float)) else 0
        )
        form.addRow("± range:", self.round_tolerance_spin)

        self.round_checkbox.toggled.connect(self._on_round_toggle)
        self.round_checkbox.setChecked(
            bool(isinstance(rounds_default, (int, float)))
        )
        self._on_round_toggle(self.round_checkbox.isChecked())
        layout.addLayout(form)

        if current_data.get("winner") == 2:
            self.army2_radio.setChecked(True)
        else:
            self.army1_radio.setChecked(True)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        clear_btn = buttons.addButton("Clear", QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        clear_btn.clicked.connect(self._clear)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        winner = 1 if self.army1_radio.isChecked() else 2
        target: SeedTarget = {}
        target["winner"] = int(winner)
        target["remaining"] = int(self.remaining_spin.value())
        if self.round_checkbox.isChecked():
            target["rounds"] = int(self.rounds_spin.value())
            target["round_tolerance"] = int(self.round_tolerance_spin.value())
        self._target = target
        self.accept()

    def _clear(self) -> None:
        self._target = None
        self.accept()

    def target(self) -> SeedTarget | None:
        """Return the selected outcome or ``None`` if cleared."""

        return self._target

    def _on_round_toggle(self, checked: bool) -> None:
        self.rounds_spin.setEnabled(checked)
        self.round_tolerance_spin.setEnabled(checked)


class StarredImageLabel(QtWidgets.QLabel):
    """QLabel that can grey out stars based on a count.

    Stars are drawn procedurally via :class:`QPainter` so the repository does
    not need to ship binary star images.  Only the star shapes are affected
    which avoids greying rectangular slices of the artwork.

    Layout ratios describe how a star strip is positioned within an image.  For
    generic skill images the stars span the full width and occupy the bottom
    ``20 %`` of the image.  Hero portraits include built-in star graphics with
    horizontal padding, so separate ratios are used.  These values can be
    overridden by placing a JSON file next to the image containing optional
    ``max_stars``, ``star_vertical_ratio`` and ``star_side_margin_ratio``
    entries.  Ratios are expressed as fractions of the full image dimensions.
    """

    # Colour used when greying out missing stars (matches previous behaviour)
    GREY_COLOR = QtGui.QColor(100, 100, 100, 180)
    DEFAULT_STAR_VERTICAL_RATIO = 0.8
    PLUGIN_STAR_VERTICAL_RATIO = 0.88
    PLUGIN_STAR_SIDE_MARGIN_RATIO = 0.0
    HERO_STAR_VERTICAL_RATIO = 0.88
    HERO_STAR_SIDE_MARGIN_RATIO = 0.04
    HERO_STAR_V_OFFSETS = (
        -0.02,
        -0.01,
        0.01,
        0.01,
        -0.01,
        -0.02,
    )
    HERO_STAR_H_OFFSETS = (0.0,) * 6
    PLUGIN_STAR_V_OFFSETS = (0.0,) * 6
    PLUGIN_STAR_H_OFFSETS = (0.0,) * 6
    PLUGIN_STAR_SIZE_FACTORS = (1.0,) * 6

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScaledContents(True)
        self._image_path: str | None = None
        self._orig_image: Image.Image | None = None

        # Default layout configuration
        self.default_max_stars: int = 6
        self.default_star_vertical_ratio: float = self.DEFAULT_STAR_VERTICAL_RATIO
        self.plugin_star_vertical_ratio: float = self.PLUGIN_STAR_VERTICAL_RATIO
        self.plugin_star_side_margin_ratio: float = self.PLUGIN_STAR_SIDE_MARGIN_RATIO
        self.hero_star_vertical_ratio: float = self.HERO_STAR_VERTICAL_RATIO
        self.hero_star_side_margin_ratio: float = self.HERO_STAR_SIDE_MARGIN_RATIO
        self.hero_star_v_offsets: tuple[float, ...] = self.HERO_STAR_V_OFFSETS
        self.hero_star_h_offsets: tuple[float, ...] = self.HERO_STAR_H_OFFSETS
        self.hero_star_size_factors: tuple[float, ...] = (1.0,) * 6
        self.plugin_star_v_offsets: tuple[float, ...] = self.PLUGIN_STAR_V_OFFSETS
        self.plugin_star_h_offsets: tuple[float, ...] = self.PLUGIN_STAR_H_OFFSETS
        self.plugin_star_size_factors: tuple[float, ...] = self.PLUGIN_STAR_SIZE_FACTORS

        self.star_color: QtGui.QColor = self.GREY_COLOR

        # runtime layout configuration that may be overridden via metadata
        self.max_stars: int = self.default_max_stars
        self.star_vertical_ratio: float = self.default_star_vertical_ratio
        self.star_side_margin_ratio: float = 0.0
        self.star_count: int = self.max_stars
        self._is_hero_image: bool = False
        self._is_plugin_image: bool = False
        # cache of star polygons keyed by their (width, height)
        self._star_polygon_cache: dict[tuple[int, int], QtGui.QPolygonF] = {}

    def set_layout(
        self,
        max_stars: int,
        vertical_ratio: float,
        side_margin: float,
        offsets: list[float] | tuple[float, ...] | None = None,
        h_offsets: list[float] | tuple[float, ...] | None = None,
        sizes: list[float] | tuple[float, ...] | None = None,
    ) -> None:
        """Override star layout and refresh the image preview."""

        target = None
        self.max_stars = max_stars
        self.star_vertical_ratio = vertical_ratio
        self.star_side_margin_ratio = side_margin
        if self._is_hero_image:
            target = "hero"
        elif self._is_plugin_image:
            target = "plugin"
        if target == "hero" and offsets is not None:
            self.hero_star_v_offsets = tuple(offsets)
        elif target == "plugin" and offsets is not None:
            self.plugin_star_v_offsets = tuple(offsets)
        if target == "hero" and h_offsets is not None:
            self.hero_star_h_offsets = tuple(h_offsets)
        elif target == "plugin" and h_offsets is not None:
            self.plugin_star_h_offsets = tuple(h_offsets)
        if target == "hero" and sizes is not None:
            self.hero_star_size_factors = tuple(sizes)
        elif target == "plugin" and sizes is not None:
            self.plugin_star_size_factors = tuple(sizes)
        self.star_count = max(0, min(self.max_stars, self.star_count))
        self._update_pixmap()

    def set_star_color(self, color: QtGui.QColor) -> None:
        """Set the colour used to draw missing stars."""
        self.star_color = color
        self._update_pixmap()

    def set_image(self, path: str | None) -> None:
        """Load image from ``path`` and reset star count."""
        self._image_path = path
        self.star_count = self.max_stars
        if path and os.path.exists(path):
            self._orig_image = Image.open(path).convert("RGBA")
            # Determine if the image is a hero portrait or a skill image
            self._is_hero_image = "Hero Images" in path
            self._is_plugin_image = "Plugin Skill Images" in path

            # Apply default layout for the image type
            self.max_stars = self.default_max_stars
            if self._is_hero_image:
                self.star_vertical_ratio = self.hero_star_vertical_ratio
                self.star_side_margin_ratio = self.hero_star_side_margin_ratio
            elif self._is_plugin_image:
                self.star_vertical_ratio = self.plugin_star_vertical_ratio
                self.star_side_margin_ratio = self.plugin_star_side_margin_ratio
            else:
                self.star_vertical_ratio = self.default_star_vertical_ratio
                self.star_side_margin_ratio = 0.0

            # Reset colour to default before applying metadata
            self.star_color = self.GREY_COLOR

            # Allow optional metadata to override layout assumptions
            meta_path = os.path.splitext(path)[0] + ".json"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as fh:
                        meta = json.load(fh)
                    self.max_stars = int(meta.get("max_stars", self.max_stars))
                    self.star_vertical_ratio = float(
                        meta.get("star_vertical_ratio", self.star_vertical_ratio)
                    )
                    self.star_side_margin_ratio = float(
                        meta.get("star_side_margin_ratio", self.star_side_margin_ratio)
                    )
                    v_off = meta.get("v_offsets")
                    h_off = meta.get("h_offsets")
                    size_fact = meta.get("size_factors")
                    color = meta.get("star_color")
                    if color is not None:
                        qcol = QtGui.QColor(color)
                        if qcol.isValid():
                            self.star_color = qcol
                    if self._is_hero_image:
                        if v_off is not None:
                            self.hero_star_v_offsets = tuple(float(x) for x in v_off)
                        if h_off is not None:
                            self.hero_star_h_offsets = tuple(float(x) for x in h_off)
                        if size_fact is not None:
                            self.hero_star_size_factors = tuple(
                                float(x) for x in size_fact
                            )
                    elif self._is_plugin_image:
                        if v_off is not None:
                            self.plugin_star_v_offsets = tuple(float(x) for x in v_off)
                        if h_off is not None:
                            self.plugin_star_h_offsets = tuple(float(x) for x in h_off)
                        if size_fact is not None:
                            self.plugin_star_size_factors = tuple(
                                float(x) for x in size_fact
                            )
                except Exception:
                    # Ignore malformed metadata files
                    pass
            self.star_count = self.max_stars
        else:
            self._orig_image = None
            self.clear()
            return
        self._update_pixmap()

    def set_star_count(self, count: int) -> None:
        self.star_count = max(0, min(self.max_stars, count))
        self._update_pixmap()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._orig_image is None:
            return
        count, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Star Count",
            f"Enter star count (0-{self.max_stars}):",
            self.star_count,
            0,
            self.max_stars,
        )
        if ok:
            self.set_star_count(count)

    def _build_star_polygon(self, width: int, height: int) -> QtGui.QPolygonF:
        """Return a four-point star polygon of ``width`` × ``height``.

        The polygon alternates outer and inner vertices every 45° producing
        eight total points. Results are cached by ``(width, height)`` to avoid
        recomputation.
        """

        key = (width, height)
        cached = self._star_polygon_cache.get(key)
        if cached is not None:
            return cached

        cx, cy = width / 2, height / 2
        outer_r = min(width, height) / 2
        # Pull the inner vertices toward the centre so the shape resembles a
        # classic four-point star rather than a simple diamond.  A value around
        # forty percent of the outer radius produces long, tapered arms similar
        # to the reference image.
        inner_r = outer_r * 0.4

        points: list[QtCore.QPointF] = []
        for i in range(8):
            angle = math.radians(-90 + i * 45)
            r = outer_r if i % 2 == 0 else inner_r
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(QtCore.QPointF(x, y))

        polygon = QtGui.QPolygonF(points)
        self._star_polygon_cache[key] = polygon
        return polygon

    def _update_pixmap(self) -> None:
        if not self._orig_image:
            self.clear()
            return

        w, h = self._orig_image.size
        buf = self._orig_image.convert("RGBA").tobytes("raw", "BGRA")
        img = QtGui.QImage(buf, w, h, QtGui.QImage.Format.Format_ARGB32).copy()

        if self.star_count < self.max_stars:
            star_width = w * (1 - 2 * self.star_side_margin_ratio) / self.max_stars
            star_height = h * (1 - self.star_vertical_ratio)
            x_offset = w * self.star_side_margin_ratio
            y_base = h - star_height

            mask = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32)
            mask.fill(QtGui.QColor(0, 0, 0, 0))
            mp = QtGui.QPainter(mask)
            mp.setPen(QtCore.Qt.PenStyle.NoPen)
            mp.setBrush(self.star_color)
            poly = self._build_star_polygon(int(star_width), int(star_height))
            for idx in range(self.star_count, self.max_stars):
                v_off = h_off = 0.0
                if self._is_hero_image:
                    if idx < len(self.hero_star_v_offsets):
                        v_off = self.hero_star_v_offsets[idx] * star_height
                    if idx < len(self.hero_star_h_offsets):
                        h_off = self.hero_star_h_offsets[idx] * star_width
                elif self._is_plugin_image:
                    if idx < len(self.plugin_star_v_offsets):
                        v_off = self.plugin_star_v_offsets[idx] * star_height
                    if idx < len(self.plugin_star_h_offsets):
                        h_off = self.plugin_star_h_offsets[idx] * star_width
                mp.save()
                mp.translate(int(x_offset + idx * star_width + h_off), int(y_base + v_off))
                mp.drawPolygon(poly)
                mp.restore()
            mp.end()

            painter = QtGui.QPainter(img)
            painter.drawImage(0, 0, mask)
            painter.end()

        pix = QtGui.QPixmap.fromImage(img)
        self.setPixmap(
            pix.scaled(self.width(), self.height(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        )


class StarOverlayDebugDialog(QtWidgets.QDialog):
    """Dialog allowing live tweaking of star overlay layout."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Star Overlay Tuner")
        layout = QtWidgets.QVBoxLayout(self)

        self.preview = StarredImageLabel()
        self.preview.setFixedSize(200, 200)
        layout.addWidget(self.preview, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        form = QtWidgets.QFormLayout()
        self.max_spin = QtWidgets.QSpinBox()
        self.max_spin.setRange(1, 12)
        form.addRow("Max Stars", self.max_spin)

        self.vert_spin = QtWidgets.QDoubleSpinBox()
        self.vert_spin.setRange(0.0, 1.0)
        self.vert_spin.setSingleStep(0.0001)
        self.vert_spin.setDecimals(4)
        form.addRow("Vertical Ratio", self.vert_spin)

        self.side_spin = QtWidgets.QDoubleSpinBox()
        self.side_spin.setRange(0.0, 0.5)
        self.side_spin.setSingleStep(0.0001)
        self.side_spin.setDecimals(4)
        form.addRow("Side Margin Ratio", self.side_spin)

        v_offsets_layout = QtWidgets.QHBoxLayout()
        self.v_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            v_offsets_layout.addWidget(spin)
            self.v_offset_spins.append(spin)
        form.addRow("Hero V Offsets", v_offsets_layout)

        h_offsets_layout = QtWidgets.QHBoxLayout()
        self.h_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            h_offsets_layout.addWidget(spin)
            self.h_offset_spins.append(spin)
        form.addRow("Hero H Offsets", h_offsets_layout)

        sizes_layout = QtWidgets.QHBoxLayout()
        self.size_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.1, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            spin.setValue(1.0)
            sizes_layout.addWidget(spin)
            self.size_spins.append(spin)
        form.addRow("Hero Size Factors", sizes_layout)

        plugin_v_layout = QtWidgets.QHBoxLayout()
        self.plugin_v_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            plugin_v_layout.addWidget(spin)
            self.plugin_v_offset_spins.append(spin)
        form.addRow("Plugin V Offsets", plugin_v_layout)

        plugin_h_layout = QtWidgets.QHBoxLayout()
        self.plugin_h_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            plugin_h_layout.addWidget(spin)
            self.plugin_h_offset_spins.append(spin)
        form.addRow("Plugin H Offsets", plugin_h_layout)

        plugin_size_layout = QtWidgets.QHBoxLayout()
        self.plugin_size_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.1, 2.0)
            spin.setSingleStep(0.0001)
            spin.setDecimals(4)
            spin.setValue(1.0)
            plugin_size_layout.addWidget(spin)
            self.plugin_size_spins.append(spin)
        form.addRow("Plugin Size Factors", plugin_size_layout)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        load_hero_btn = QtWidgets.QPushButton("Load Hero Image")
        load_plugin_btn = QtWidgets.QPushButton("Load Plugin Image")
        save_btn = QtWidgets.QPushButton("Save Layout")
        color_btn = QtWidgets.QPushButton("Star Color")
        btn_row.addWidget(load_hero_btn)
        btn_row.addWidget(load_plugin_btn)
        btn_row.addWidget(color_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # signal wiring
        self.max_spin.valueChanged.connect(partial(self._update_from_spins, None))
        self.vert_spin.valueChanged.connect(partial(self._update_from_spins, None))
        self.side_spin.valueChanged.connect(partial(self._update_from_spins, None))
        for spin in self.v_offset_spins + self.h_offset_spins + self.size_spins:
            spin.valueChanged.connect(partial(self._update_from_spins, False))
        for spin in (
            self.plugin_v_offset_spins
            + self.plugin_h_offset_spins
            + self.plugin_size_spins
        ):
            spin.valueChanged.connect(partial(self._update_from_spins, True))
        load_hero_btn.clicked.connect(self._load_hero)
        load_plugin_btn.clicked.connect(self._load_plugin)
        color_btn.clicked.connect(self._pick_color)
        save_btn.clicked.connect(self._save_layout)

    # --- helpers -----------------------------------------------------
    def _apply_spins_from_label(self) -> None:
        self.max_spin.blockSignals(True)
        self.vert_spin.blockSignals(True)
        self.side_spin.blockSignals(True)
        for spin in (
            self.v_offset_spins
            + self.h_offset_spins
            + self.size_spins
            + self.plugin_v_offset_spins
            + self.plugin_h_offset_spins
            + self.plugin_size_spins
        ):
            spin.blockSignals(True)

        self.max_spin.setValue(self.preview.max_stars)
        self.vert_spin.setValue(self.preview.star_vertical_ratio)
        self.side_spin.setValue(self.preview.star_side_margin_ratio)
        for i, spin in enumerate(self.v_offset_spins):
            val = 0.0
            if i < len(self.preview.hero_star_v_offsets):
                val = self.preview.hero_star_v_offsets[i]
            spin.setValue(val)
        for i, spin in enumerate(self.h_offset_spins):
            val = 0.0
            if i < len(self.preview.hero_star_h_offsets):
                val = self.preview.hero_star_h_offsets[i]
            spin.setValue(val)
        for i, spin in enumerate(self.size_spins):
            val = 1.0
            if i < len(self.preview.hero_star_size_factors):
                val = self.preview.hero_star_size_factors[i]
            spin.setValue(val)
        for i, spin in enumerate(self.plugin_v_offset_spins):
            val = 0.0
            if i < len(self.preview.plugin_star_v_offsets):
                val = self.preview.plugin_star_v_offsets[i]
            spin.setValue(val)
        for i, spin in enumerate(self.plugin_h_offset_spins):
            val = 0.0
            if i < len(self.preview.plugin_star_h_offsets):
                val = self.preview.plugin_star_h_offsets[i]
            spin.setValue(val)
        for i, spin in enumerate(self.plugin_size_spins):
            val = 1.0
            if i < len(self.preview.plugin_star_size_factors):
                val = self.preview.plugin_star_size_factors[i]
            spin.setValue(val)

        self.max_spin.blockSignals(False)
        self.vert_spin.blockSignals(False)
        self.side_spin.blockSignals(False)
        for spin in (
            self.v_offset_spins
            + self.h_offset_spins
            + self.size_spins
            + self.plugin_v_offset_spins
            + self.plugin_h_offset_spins
            + self.plugin_size_spins
        ):
            spin.blockSignals(False)

    def _update_from_spins(self, plugin: bool | None, *_args) -> None:
        if plugin is True and not self.preview._is_plugin_image:
            return
        if plugin is False and not self.preview._is_hero_image:
            return
        if plugin is None:
            plugin = self.preview._is_plugin_image
        if plugin:
            v_offsets = [spin.value() for spin in self.plugin_v_offset_spins]
            h_offsets = [spin.value() for spin in self.plugin_h_offset_spins]
            sizes = [spin.value() for spin in self.plugin_size_spins]
        else:
            v_offsets = [spin.value() for spin in self.v_offset_spins]
            h_offsets = [spin.value() for spin in self.h_offset_spins]
            sizes = [spin.value() for spin in self.size_spins]
        self.preview.set_layout(
            self.max_spin.value(),
            self.vert_spin.value(),
            self.side_spin.value(),
            offsets=v_offsets,
            h_offsets=h_offsets,
            sizes=sizes,
        )

    def _pick_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            self.preview.star_color, self, "Select Star Color"
        )
        if color.isValid():
            self.preview.set_star_color(color)

    def _load_hero(self) -> None:
        hero_dir = os.path.join(os.path.dirname(__file__), "Hero Images")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Hero Image", hero_dir, "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.preview.set_image(path)
            self._apply_spins_from_label()

    def _load_plugin(self) -> None:
        plugin_dir = os.path.join(os.path.dirname(__file__), "Plugin Skill Images")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Plugin Image", plugin_dir, "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.preview.set_image(path)
            self._apply_spins_from_label()

    def _save_layout(self) -> None:
        if not self.preview._image_path:
            return
        data = {
            "max_stars": self.preview.max_stars,
            "star_vertical_ratio": self.preview.star_vertical_ratio,
            "star_side_margin_ratio": self.preview.star_side_margin_ratio,
            "star_color": self.preview.star_color.name(
                QtGui.QColor.NameFormat.HexArgb
            ),
        }
        if self.preview._is_hero_image:
            data.update(
                {
                    "v_offsets": list(self.preview.hero_star_v_offsets),
                    "h_offsets": list(self.preview.hero_star_h_offsets),
                    "size_factors": list(self.preview.hero_star_size_factors),
                }
            )
        elif self.preview._is_plugin_image:
            data.update(
                {
                    "v_offsets": list(self.preview.plugin_star_v_offsets),
                    "h_offsets": list(self.preview.plugin_star_h_offsets),
                    "size_factors": list(self.preview.plugin_star_size_factors),
                }
            )
        meta_path = os.path.splitext(self.preview._image_path)[0] + ".json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

        # Propagate settings to all images of the same type
        base_dir = None
        if self.preview._is_hero_image:
            base_dir = os.path.join(os.path.dirname(__file__), "Hero Images")
        elif self.preview._is_plugin_image:
            base_dir = os.path.join(os.path.dirname(__file__), "Plugin Skill Images")
        if base_dir and os.path.isdir(base_dir):
            for fname in os.listdir(base_dir):
                if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                    target = os.path.join(
                        base_dir, os.path.splitext(fname)[0] + ".json"
                    )
                    with open(target, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2)

        # Reload to confirm
        self.preview.set_image(self.preview._image_path)
        self._apply_spins_from_label()


class PaletteListWidget(QtWidgets.QListWidget):
    """Palette providing drag sources for PDF layout items."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setIconSize(QtCore.QSize(128, 128))
        self.setDragEnabled(True)

    def startDrag(self, supportedActions: QtCore.Qt.DropActions) -> None:  # type: ignore[override]
        item = self.currentItem()
        if item is None:
            return
        mime = QtCore.QMimeData()
        item_type = str(item.data(QtCore.Qt.ItemDataRole.UserRole))
        mime.setText(item_type)
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(item.icon().pixmap(self.iconSize()))
        drag.exec(supportedActions)


class PageLayoutWidget(QtWidgets.QGraphicsView):
    """Graphics view representing a single PDF page for layout."""

    def __init__(self, pixmap_getter, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._get_pixmap = pixmap_getter
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore[override]
        item_type = event.mimeData().text()
        pix = self._get_pixmap(item_type)
        if pix is None or pix.isNull():
            return
        item = QtWidgets.QGraphicsPixmapItem(pix)
        flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
        item.setFlags(flags.ItemIsMovable | flags.ItemIsSelectable)
        pos = self.mapToScene(event.position().toPoint())
        item.setPos(pos)
        item.setData(0, item_type)
        self.scene().addItem(item)
        event.acceptProposedAction()

    def add_item(self, item_type: str, x: float, y: float) -> None:
        """Convenience helper to insert an item at coordinates (x, y)."""
        pix = self._get_pixmap(item_type)
        if pix is None or pix.isNull():
            return
        item = QtWidgets.QGraphicsPixmapItem(pix)
        flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
        item.setFlags(flags.ItemIsMovable | flags.ItemIsSelectable)
        item.setPos(x, y)
        item.setData(0, item_type)
        self.scene().addItem(item)

    def serialize(self) -> dict:
        data: list[dict] = []
        for item in self.scene().items():
            if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                entry = {
                    "type": item.data(0),
                    "x": float(item.x()),
                    "y": float(item.y()),
                }
                if item.scale() != 1.0:
                    entry["scale"] = float(item.scale())
                data.append(entry)
        return {"items": data}

    def load(self, items: list[dict]) -> None:
        self.scene().clear()
        for entry in items:
            itype = entry.get("type")
            if not isinstance(itype, str):
                continue
            pix = self._get_pixmap(itype)
            if pix is None or pix.isNull():
                continue
            item = QtWidgets.QGraphicsPixmapItem(pix)
            flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
            item.setFlags(flags.ItemIsMovable | flags.ItemIsSelectable)
            item.setPos(float(entry.get("x", 0)), float(entry.get("y", 0)))
            if "scale" in entry:
                try:
                    item.setScale(float(entry["scale"]))
                except (TypeError, ValueError):
                    pass
            item.setData(0, itype)
            self.scene().addItem(item)

class PDFLayoutDialog(QtWidgets.QDialog):
    """Dialog allowing configuration of multi-page PDF export layout."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PDF Layout Tool")
        self._main_window = parent  # type: ignore[assignment]

        self.pages: list[dict] = load_pdf_layout()
        layout = QtWidgets.QVBoxLayout(self)

        self._count_spin = QtWidgets.QSpinBox()
        self._count_spin.setRange(1, 20)
        self._count_spin.setValue(len(self.pages))
        self._count_spin.valueChanged.connect(self._adjust_pages)
        layout.addWidget(QtWidgets.QLabel("Number of pages:"))
        layout.addWidget(self._count_spin)

        hbox = QtWidgets.QHBoxLayout()
        layout.addLayout(hbox, 1)

        self.palette = PaletteListWidget()
        hbox.addWidget(self.palette)

        self.tab_widget = QtWidgets.QTabWidget()
        hbox.addWidget(self.tab_widget, 1)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save_layout)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._page_widgets: list[PageLayoutWidget] = []
        self._populate_palette()
        self._populate_tabs()

    def _populate_palette(self) -> None:
        self.palette.clear()
        if self._main_window is None:
            return
        items = self._main_window.get_histogram_pixmaps()
        preview = self._main_window.render_preview_pixmap()
        if preview is not None:
            items = {"preview": preview, **items}
        items["army_composition"] = self._main_window._render_army_composition_pixmap()
        for key, pix in items.items():
            icon = QtGui.QIcon(pix)
            text = key.replace("_", " ").title()
            lw_item = QtWidgets.QListWidgetItem(icon, text)
            lw_item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.palette.addItem(lw_item)

    def _adjust_pages(self, count: int) -> None:
        while len(self.pages) < count:
            self.pages.append({"items": []})
        while len(self.pages) > count:
            self.pages.pop()
        self._populate_tabs()

    def _populate_tabs(self) -> None:
        self.tab_widget.clear()
        self._page_widgets.clear()
        for idx, page in enumerate(self.pages, start=1):
            widget = PageLayoutWidget(self._main_window.get_pdf_item_pixmap)  # type: ignore[arg-type]
            widget.load(page.get("items", []))
            self.tab_widget.addTab(widget, f"Page {idx}")
            self._page_widgets.append(widget)

    def _save_layout(self) -> None:
        pages = [w.serialize() for w in self._page_widgets]
        save_pdf_layout(pages)
        self.accept()


class DynamicUnrevivableDialog(QtWidgets.QDialog):
    """Dialog exposing coefficients for dynamic unrevivable calculations."""

    settings_applied = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dynamic Unrevivable Ratios")

        main_layout = QtWidgets.QVBoxLayout(self)
        self._type_setting_spins: dict[str, dict[str, QtWidgets.QDoubleSpinBox]] = {}

        type_fields = (
            ("Combat (Basic) base", "combat_basic_base"),
            ("Combat (Basic) bonus multiplier", "combat_basic_bonus_multiplier"),
            ("Combat (Counter) base", "combat_counter_base"),
            ("Combat (Counter) bonus multiplier", "combat_counter_bonus_multiplier"),
            ("Skill base", "skill_base"),
            ("Skill bonus multiplier", "skill_bonus_multiplier"),
            ("Non-mutual base", "non_mutual_base"),
            ("Non-mutual bonus multiplier", "non_mutual_bonus_multiplier"),
        )

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        for unit_type in ("pikemen", "archers", "infantry"):
            group = QtWidgets.QGroupBox(f"{unit_type.capitalize()} attacker settings")
            form = QtWidgets.QFormLayout(group)
            field_spins: dict[str, QtWidgets.QDoubleSpinBox] = {}
            for label, key in type_fields:
                spin = self._make_percent_spin()
                form.addRow(label, spin)
                field_spins[key] = spin
            self._type_setting_spins[unit_type] = field_spins
            content_layout.addWidget(group)
        content_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        main_layout.addWidget(self._status)

        btn_row = QtWidgets.QHBoxLayout()
        main_layout.addLayout(btn_row)
        session_btn = QtWidgets.QPushButton("Session Apply")
        session_btn.clicked.connect(self._apply_session)
        btn_row.addWidget(session_btn)

        save_btn = QtWidgets.QPushButton("Universal Save")
        save_btn.clicked.connect(self._save_universal)
        btn_row.addWidget(save_btn)

        reset_btn = QtWidgets.QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch(1)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self._load_current_settings()

    @staticmethod
    def _make_percent_spin() -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 300.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setSuffix(" %")
        return spin

    def _load_current_settings(self) -> None:
        settings = dynamic_unrevivable_config.get_settings()
        for unit_type, spins in self._type_setting_spins.items():
            for key, spin in spins.items():
                setting_key = f"{unit_type}_{key}"
                spin.setValue(settings[setting_key] * 100.0)

    def _gather_settings(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for unit_type, spins in self._type_setting_spins.items():
            for key, spin in spins.items():
                setting_key = f"{unit_type}_{key}"
                values[setting_key] = spin.value() / 100.0
        return values

    def _apply_session(self) -> None:
        settings = self._gather_settings()
        dynamic_unrevivable_config.apply_session_settings(settings)
        self._status.setText(
            "Session overrides applied. These values reset on restart."
        )
        self.settings_applied.emit()

    def _save_universal(self) -> None:
        try:
            dynamic_unrevivable_config.save_universal_settings(
                self._gather_settings()
            )
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self._status.setText("Universal overrides saved to disk.")
        self._load_current_settings()
        self.settings_applied.emit()

    def _reset_defaults(self) -> None:
        dynamic_unrevivable_config.reset_to_defaults()
        self._load_current_settings()
        self._status.setText("Dynamic ratios reset to defaults.")
        self.settings_applied.emit()


class TroopScalarDialog(QtWidgets.QDialog):
    """Dialog for adjusting the global troop scalar multiplier."""

    multiplier_applied = QtCore.pyqtSignal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Troop Scalar Multiplier")

        layout = QtWidgets.QVBoxLayout(self)

        description = QtWidgets.QLabel(
            "Adjust the multiplier applied to troop-based calculations."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._spin = QtWidgets.QDoubleSpinBox()
        self._spin.setRange(0.0, 1000.0)
        self._spin.setDecimals(3)
        self._spin.setSingleStep(0.05)
        self._spin.setValue(troop_scalar_config.get_multiplier())
        layout.addWidget(self._spin)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        session_btn = QtWidgets.QPushButton("Session Apply")
        session_btn.clicked.connect(self._apply_session)
        btn_row.addWidget(session_btn)

        save_btn = QtWidgets.QPushButton("Save")
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(save_btn)

        reset_btn = QtWidgets.QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_to_default)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch(1)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        color = "#ff6666" if error else "#66ff99"
        self._status.setStyleSheet(f"color: {color};")
        self._status.setText(message)

    def _emit_multiplier(self, value: float) -> None:
        self.multiplier_applied.emit(float(value))

    def _apply_session(self) -> None:
        try:
            value = troop_scalar_config.set_session_multiplier(self._spin.value())
        except ValueError as exc:  # pragma: no cover - GUI feedback
            self._set_status(str(exc), error=True)
            return
        self._set_status(f"Session multiplier set to {value:.3f}")
        self._emit_multiplier(value)

    def _save_and_close(self) -> None:
        try:
            value = troop_scalar_config.save_multiplier(self._spin.value())
        except ValueError as exc:  # pragma: no cover - GUI feedback
            self._set_status(str(exc), error=True)
            return
        self._set_status(f"Multiplier saved at {value:.3f}")
        self._spin.setValue(value)
        self._emit_multiplier(value)
        self.accept()

    def _reset_to_default(self) -> None:
        value = troop_scalar_config.reset_to_default()
        self._spin.setValue(value)
        self._set_status("Multiplier reset to default")
        self._emit_multiplier(value)
        self.accept()
        self._status.clear()

PathComponent = str | int


class SkillParamEditor(QtWidgets.QWidget):
    """Widget providing spin boxes for configurable skill parameters."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QtWidgets.QFormLayout(self)
        self._fields: dict[tuple[PathComponent, ...], QtWidgets.QDoubleSpinBox] = {}
        self._defaults: dict[tuple[PathComponent, ...], float] = {}
        self._skill_id: str | None = None
        self._base_definition: dict[str, Any] | None = None

    def set_skill(self, skill_id: str | None, overrides: dict | None = None) -> None:
        """Populate editors for ``skill_id`` using optional ``overrides``."""
        # Save current overrides before switching
        self.clear()
        self._skill_id = skill_id or None
        self._base_definition = None
        if not skill_id:
            return
        sdef = SKILL_REGISTRY_GLOBAL.get(skill_id)
        if not sdef:
            return
        self._base_definition = copy.deepcopy(sdef)
        overrides = overrides or {}
        # Trigger chance
        tc = sdef.get("trigger_chance")
        if isinstance(tc, (int, float)):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setDecimals(6)
            spin.setSingleStep(0.0001)
            spin.setValue(overrides.get("trigger_chance", tc))
            self._layout.addRow("Trigger Chance", spin)
            self._fields[("trigger_chance",)] = spin
            self._defaults[("trigger_chance",)] = float(tc)

        def walk(value: Any, path: tuple[PathComponent, ...], override_value: Any) -> None:
            if isinstance(value, dict):
                ov_dict = override_value if isinstance(override_value, dict) else {}
                for key, sub_value in value.items():
                    next_path = path + (key,)
                    if next_path == ("trigger_chance",):
                        continue
                    walk(sub_value, next_path, ov_dict.get(key))
            elif isinstance(value, list):
                overrides_map: dict[int, Any] = {}
                if isinstance(override_value, list):
                    overrides_map = {
                        idx: override_value[idx]
                        for idx in range(len(override_value))
                        if idx < len(value)
                    }
                elif isinstance(override_value, dict):
                    for raw_idx, ov_item in override_value.items():
                        try:
                            idx = int(raw_idx)
                        except (TypeError, ValueError):
                            continue
                        if idx < 0 or idx >= len(value):
                            continue
                        overrides_map[idx] = ov_item
                for index, item in enumerate(value):
                    override_item = overrides_map.get(index)
                    walk(item, path + (index,), override_item)
            else:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    default_val = float(value)
                    override_val = (
                        float(override_value)
                        if isinstance(override_value, (int, float)) and not isinstance(override_value, bool)
                        else None
                    )
                    self._create_numeric_field(path, default_val, override_val)

        walk(sdef, tuple(), overrides)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields.clear()
        self._defaults.clear()
        self._base_definition = None

    def get_overrides(self) -> dict:
        if not self._base_definition:
            return {}

        base_copy = copy.deepcopy(self._base_definition)
        modified = copy.deepcopy(self._base_definition)
        changed = False

        for path, spin in self._fields.items():
            val = float(spin.value())
            default = self._defaults.get(path)
            if default is not None and math.isclose(val, default, rel_tol=1e-9, abs_tol=1e-9):
                continue
            self._set_path_value(modified, path, val)
            changed = True

        if not changed:
            return {}

        diff = self._diff_structures(base_copy, modified)
        return diff if isinstance(diff, dict) else {}

    def _create_numeric_field(
        self,
        path: tuple[PathComponent, ...],
        default: float,
        override: float | None,
    ) -> None:
        label = self._format_label(path)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-1e9, 1e9)
        spin.setDecimals(6)
        spin.setSingleStep(0.0001)
        spin.setValue(override if override is not None else default)
        self._layout.addRow(label, spin)
        self._fields[path] = spin
        self._defaults[path] = default

    @staticmethod
    def _format_label(path: tuple[PathComponent, ...]) -> str:
        parts: list[str] = []
        for component in path:
            if isinstance(component, int):
                if parts:
                    parts[-1] = f"{parts[-1]}[{component}]"
                else:
                    parts.append(f"[{component}]")
            else:
                parts.append(str(component))
        return " / ".join(parts) if parts else ""

    @staticmethod
    def _set_path_value(container: Any, path: tuple[PathComponent, ...], value: float) -> None:
        current = container
        for component in path[:-1]:
            current = current[component]
        last = path[-1]
        current[last] = value

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
        return a == b

    @classmethod
    def _diff_structures(cls, base: Any, modified: Any) -> Any | None:
        return diff_structures(base, modified)


class BonusStatsDialog(QtWidgets.QDialog):
    """Dialog allowing users to edit additive bonus stats for an army."""

    def __init__(
        self,
        bonus_stats: dict[str, Any],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bonus Stats")

        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Values are additive. Use decimals (e.g., 0.3 for +30%). "
            "Positive values increase boosts while damage reductions subtract from incoming damage. "
            "All manual bonus stats are permanent and cannot be dispelled or cleansed."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._spin_boxes: dict[tuple[str, ...], QtWidgets.QDoubleSpinBox] = {}

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        normalized = merge_bonus_stats(default_bonus_stats(), bonus_stats or {})

        self._add_group(
            content_layout,
            "Damage Reduction",
            [
                ("Overall", ("damage_reduction", "all")),
                ("vs Pikemen", ("damage_reduction", "vs_pikemen")),
                ("vs Archers", ("damage_reduction", "vs_archers")),
                ("vs Infantry", ("damage_reduction", "vs_infantry")),
                ("vs Reactive Skills", ("damage_reduction", "reactive")),
                ("vs Cooperation Skills", ("damage_reduction", "cooperation")),
                ("vs Command Skills", ("damage_reduction", "command")),
            ],
            normalized,
        )

        self._add_group(
            content_layout,
            "Damage Boosts",
            [
                ("Overall", ("damage_boost", "all")),
                ("vs Pikemen", ("damage_boost", "vs_pikemen")),
                ("vs Archers", ("damage_boost", "vs_archers")),
                ("vs Infantry", ("damage_boost", "vs_infantry")),
                ("Basic Attack Boost", ("basic_boost",)),
                ("Counterattack Boost", ("counter_boost",)),
                ("Reactive Skill Damage Boost", ("reactive_skill_boost",)),
                ("Rage Skill Damage Boost", ("rage_skill_boost",)),
                ("Cooperation Skill Damage Boost", ("cooperation_skill_boost",)),
                ("Command Skill Damage Boost", ("command_skill_boost",)),
                (
                    "Reactive Skill Critical Rate",
                    ("damage_boost", "reactive_crit_rate"),
                ),
                (
                    "Cooperation Skill Critical Rate",
                    ("damage_boost", "cooperation_crit_rate"),
                ),
                (
                    "Command Skill Critical Rate",
                    ("damage_boost", "command_crit_rate"),
                ),
            ],
            normalized,
        )

        self._add_group(
            content_layout,
            "Applied Effects Boosts",
            [
                ("Shield Gain Boost", ("shield_gain",)),
                ("Burn Boost", ("burn_boost",)),
                ("Poison Boost", ("poison_boost",)),
                ("Lacerate Boost", ("lacerate_boost",)),
            ],
            normalized,
        )

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _make_spin_box(self) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-5.0, 5.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.01)
        return spin

    def _add_group(
        self,
        parent_layout: QtWidgets.QVBoxLayout,
        title: str,
        fields: list[tuple[str, tuple[str, ...]]],
        stats: dict[str, Any],
    ) -> None:
        group = QtWidgets.QGroupBox(title)
        form = QtWidgets.QFormLayout(group)
        form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        for label, path in fields:
            spin = self._make_spin_box()
            spin.setValue(self._lookup_value(stats, path))
            form.addRow(f"{label}:", spin)
            self._spin_boxes[path] = spin
        parent_layout.addWidget(group)

    def _lookup_value(self, stats: dict[str, Any], path: tuple[str, ...]) -> float:
        current: Any = stats
        for key in path:
            if not isinstance(current, dict):
                return 0.0
            current = current.get(key, 0.0)
        try:
            return float(current)
        except (TypeError, ValueError):
            return 0.0

    def result(self) -> dict[str, Any]:
        updated = default_bonus_stats()
        for path, spin in self._spin_boxes.items():
            if len(path) == 1:
                updated[path[0]] = float(spin.value())
            elif len(path) == 2:
                updated[path[0]][path[1]] = float(spin.value())
        return updated


class JewelSkillsDialog(QtWidgets.QDialog):
    """Dialog for selecting jewel skills per slot."""

    def __init__(
        self,
        selected: dict[str, str] | None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Jewel Skills")
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Select one skill for each jewel slot. Legendary and Epic variants share mechanics "
            "with adjusted potency. Skills will trigger automatically based on their described timings."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(container)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._combos: dict[str, QtWidgets.QComboBox] = {}
        current = selected or {}
        for slot_key, slot_label in JEWEL_SLOTS:
            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
            options = gem_skill_options_for_slot(slot_key)
            for name, sid in options:
                combo.addItem(name, sid)
            completer = QtWidgets.QCompleter([name for name, _ in options], combo)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
            combo.setCompleter(completer)
            selected_id = current.get(slot_key, "")
            if selected_id:
                idx = combo.findData(selected_id)
                if idx == -1:
                    display_name = SKILL_REGISTRY_GLOBAL.get(selected_id, {}).get("name", selected_id)
                    combo.addItem(display_name, selected_id)
                    idx = combo.count() - 1
                combo.setCurrentIndex(idx)
            form.addRow(f"{slot_label}:", combo)
            self._combos[slot_key] = combo

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def result(self) -> dict[str, str]:
        selections: dict[str, str] = {}
        for slot, combo in self._combos.items():
            skill_id = combo.currentData()
            if isinstance(skill_id, str) and skill_id:
                selections[slot] = skill_id
        return selections


class MountSkillsDialog(QtWidgets.QDialog):
    """Dialog for assigning up to two mount skills per hero.

    Mount skills can have their parameters tweaked temporarily using the same
    override controls as other skill types.
    """

    def __init__(
        self,
        selected: dict[int, list[str]] | None,
        hero_names: dict[int, str],
        overrides: dict[int, dict[str, dict]] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mount Skills")
        self.setModal(True)
        self._slot_boxes: dict[tuple[int, int], QtWidgets.QComboBox] = {}
        self._param_editors: dict[tuple[int, int], SkillParamEditor] = {}

        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Assign up to two mount skills to each hero. Mount skills trigger automatically based on their description."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(container)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        options: list[tuple[str, str]] = []
        for sid, sdef in SKILL_REGISTRY_GLOBAL.items():
            if _is_mount_skill(sid):
                options.append((sdef.get("name", sid), sid))
        options.sort(key=lambda item: item[0])
        options.insert(0, ("None", ""))

        current = selected or {}
        for hero_idx in (1, 2):
            hero_display = hero_names.get(hero_idx) or f"Hero {hero_idx}"
            for slot_idx in range(2):
                combo = QtWidgets.QComboBox()
                combo.setEditable(True)
                combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
                for name, sid in options:
                    combo.addItem(name, sid)
                completer = QtWidgets.QCompleter([name for name, _ in options], combo)
                completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
                completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
                combo.setCompleter(completer)

                selected_ids = current.get(hero_idx, []) or []
                if slot_idx < len(selected_ids):
                    sid = selected_ids[slot_idx]
                    idx = combo.findData(sid)
                    if idx == -1 and sid:
                        display_name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", sid)
                        combo.addItem(display_name, sid)
                        idx = combo.count() - 1
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                param_editor = SkillParamEditor()
                current_overrides = (overrides or {}).get(hero_idx, {}).get(
                    selected_ids[slot_idx] if slot_idx < len(selected_ids) else "",
                    None,
                )
                param_editor.set_skill(
                    selected_ids[slot_idx] if slot_idx < len(selected_ids) else "",
                    current_overrides,
                )
                combo.currentIndexChanged.connect(
                    lambda _i, c=combo, e=param_editor: e.set_skill(c.currentData())
                )

                label_text = f"{hero_display} • Slot {slot_idx + 1}:"
                form.addRow(label_text, combo)
                form.addRow("", param_editor)
                self._slot_boxes[(hero_idx, slot_idx)] = combo
                self._param_editors[(hero_idx, slot_idx)] = param_editor

            if hero_display in {"", "None"}:
                for slot_idx in range(2):
                    self._slot_boxes[(hero_idx, slot_idx)].setEnabled(False)
                    self._param_editors[(hero_idx, slot_idx)].setEnabled(False)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def result(self) -> tuple[dict[int, list[str]], dict[int, dict[str, dict]]]:
        selections: dict[int, list[str]] = {1: [], 2: []}
        overrides: dict[int, dict[str, dict]] = {1: {}, 2: {}}
        for hero_idx in (1, 2):
            for slot_idx in range(2):
                combo = self._slot_boxes.get((hero_idx, slot_idx))
                editor = self._param_editors.get((hero_idx, slot_idx))
                if combo is None or editor is None or not combo.isEnabled():
                    continue
                sid = combo.currentData()
                if isinstance(sid, str) and sid:
                    selections[hero_idx].append(sid)
                    ov = editor.get_overrides()
                    if ov:
                        overrides[hero_idx][sid] = ov
        return selections, overrides


class GearSelectionDialog(QtWidgets.QDialog):
    """Dialog for assigning gear to each hero slot."""

    def __init__(
        self,
        hero_names: list[str],
        current_gear: dict[int, dict[str, str]] | None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Gear")
        self.setModal(True)
        self._slot_boxes: dict[tuple[int, str], QtWidgets.QComboBox] = {}
        self._hero_enabled: dict[int, bool] = {}

        layout = QtWidgets.QVBoxLayout(self)

        normalized_current: dict[int, dict[str, str]] = {1: {}, 2: {}}
        if current_gear:
            for hero_idx, gear_map in current_gear.items():
                if hero_idx not in normalized_current or not isinstance(gear_map, dict):
                    continue
                for slot_key, raw_value in gear_map.items():
                    slot_name = normalize_gear_slot(slot_key)
                    if not slot_name:
                        continue
                    gear_def = resolve_gear(raw_value)
                    if not gear_def or gear_def.slot != slot_name:
                        continue
                    normalized_current[hero_idx][slot_name] = gear_def.id

        gear_by_slot: dict[str, list] = {}
        for gear_def in GEAR_REGISTRY.values():
            gear_by_slot.setdefault(gear_def.slot, []).append(gear_def)
        for slot_items in gear_by_slot.values():
            slot_items.sort(
                key=lambda g: (
                    _RARITY_SORT_ORDER.get(g.rarity, 99),
                    g.name,
                )
            )

        for hero_idx, hero_name in enumerate(hero_names, start=1):
            display_name = hero_name or "None"
            group = QtWidgets.QGroupBox(f"Hero {hero_idx}: {display_name}")
            form = QtWidgets.QFormLayout(group)
            form.setFieldGrowthPolicy(
                QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )
            hero_active = display_name not in {"", "None"}
            self._hero_enabled[hero_idx] = hero_active

            for slot_key, slot_label in GEAR_SLOT_ORDER:
                combo = QtWidgets.QComboBox()
                combo.setEditable(True)
                combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
                combo.addItem("None", "")
                options = gear_by_slot.get(slot_key, [])
                completer_items: list[str] = ["None"]
                for gear_def in options:
                    display = f"{gear_def.name} ({gear_def.rarity})"
                    combo.addItem(display, gear_def.id)
                    completer_items.append(display)
                    tooltip_lines = [display]
                    tooltip_lines.extend(gear_def.effect_descriptions())
                    combo.setItemData(
                        combo.count() - 1,
                        "\n".join(tooltip_lines),
                        QtCore.Qt.ItemDataRole.ToolTipRole,
                    )
                completer = QtWidgets.QCompleter(completer_items, combo)
                completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
                completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
                combo.setCompleter(completer)

                current_id = normalized_current.get(hero_idx, {}).get(slot_key, "")
                if current_id:
                    idx = combo.findData(current_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.setEnabled(hero_active)
                form.addRow(f"{slot_label}:", combo)
                self._slot_boxes[(hero_idx, slot_key)] = combo

            layout.addWidget(group)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def result(self) -> dict[int, dict[str, str]]:
        selections: dict[int, dict[str, str]] = {}
        for (hero_idx, slot_key), combo in self._slot_boxes.items():
            if not self._hero_enabled.get(hero_idx, True):
                continue
            gear_id = combo.currentData()
            if not isinstance(gear_id, str) or not gear_id:
                continue
            selections.setdefault(hero_idx, {})[slot_key] = gear_id
        return selections


class HeroEditDialog(QtWidgets.QDialog):
    """Dialog to edit or create a hero configuration."""

    def __init__(self, hero_config: dict | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Hero")
        self.setModal(True)

        outer_layout = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(container)
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

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
        self.mount_boxes: list[QtWidgets.QComboBox] = []
        self.talent_param_editors: list[SkillParamEditor] = []
        self.base_param_editors: list[SkillParamEditor] = []
        self.plugin_param_editors: list[SkillParamEditor] = []
        self.mount_param_editors: list[SkillParamEditor] = []
        overrides_map = hero_config.get("skill_overrides", {}) if hero_config else {}

        talent_opts = _skill_options(SkillType.TALENT)
        base_opts = _skill_options(SkillType.BASE_SKILL)
        plugin_opts = _skill_options(SkillType.PLUGIN_SKILL)
        mount_opts = _skill_options(SkillType.MOUNT_SKILL)

        for i in range(3):
            box = QtWidgets.QComboBox()
            for name, sid in talent_opts:
                box.addItem(name, sid)
            box.setEditable(True)
            completer = QtWidgets.QCompleter([n for n, _ in talent_opts], box)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            box.setCompleter(completer)
            param_editor = SkillParamEditor()
            sid = ""
            if hero_config and i < len(hero_config.get("talent_ids", [])):
                sid = hero_config["talent_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.talent_boxes.append(box)
            self.talent_param_editors.append(param_editor)
            param_editor.set_skill(sid, overrides_map.get(sid))
            box.currentIndexChanged.connect(
                lambda _i, b=box, e=param_editor: e.set_skill(b.currentData())
            )
            layout.addRow(f"Talent {i+1}:", box)
            layout.addRow("", param_editor)

        for i in range(2):
            box = QtWidgets.QComboBox()
            for name, sid in base_opts:
                box.addItem(name, sid)
            box.setEditable(True)
            completer = QtWidgets.QCompleter([n for n, _ in base_opts], box)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            box.setCompleter(completer)
            param_editor = SkillParamEditor()
            sid = ""
            if hero_config and i < len(hero_config.get("base_skill_ids", [])):
                sid = hero_config["base_skill_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.base_boxes.append(box)
            self.base_param_editors.append(param_editor)
            param_editor.set_skill(sid, overrides_map.get(sid))
            box.currentIndexChanged.connect(
                lambda _i, b=box, e=param_editor: e.set_skill(b.currentData())
            )
            layout.addRow(f"Base Skill {i+1}:", box)
            layout.addRow("", param_editor)

        for i in range(2):
            box = QtWidgets.QComboBox()
            for name, sid in plugin_opts:
                box.addItem(name, sid)
            box.setEditable(True)
            completer = QtWidgets.QCompleter([n for n, _ in plugin_opts], box)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            box.setCompleter(completer)
            param_editor = SkillParamEditor()
            sid = ""
            if hero_config and i < len(hero_config.get("plugin_skill_ids", [])):
                sid = hero_config["plugin_skill_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.plugin_boxes.append(box)
            self.plugin_param_editors.append(param_editor)
            param_editor.set_skill(sid, overrides_map.get(sid))
            box.currentIndexChanged.connect(
                lambda _i, b=box, e=param_editor: e.set_skill(b.currentData())
            )
            layout.addRow(f"Plugin Skill {i+1}:", box)
            layout.addRow("", param_editor)

        for i in range(2):
            box = QtWidgets.QComboBox()
            for name, sid in mount_opts:
                box.addItem(name, sid)
            box.setEditable(True)
            completer = QtWidgets.QCompleter([n for n, _ in mount_opts], box)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            box.setCompleter(completer)
            param_editor = SkillParamEditor()
            sid = ""
            if hero_config and i < len(hero_config.get("mount_skill_ids", [])):
                sid = hero_config["mount_skill_ids"][i]
                name = SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None")
                idx = box.findText(name)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            self.mount_boxes.append(box)
            self.mount_param_editors.append(param_editor)
            param_editor.set_skill(sid, overrides_map.get(sid))
            box.currentIndexChanged.connect(
                lambda _i, b=box, e=param_editor: e.set_skill(b.currentData())
            )
            layout.addRow(f"Mount Skill {i+1}:", box)
            layout.addRow("", param_editor)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer_layout.addWidget(btns)

    def result_config(self) -> dict | None:
        if self.result() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        overrides: dict[str, dict] = {}
        for box, editor in zip(self.talent_boxes, self.talent_param_editors):
            sid = box.currentData() or ""
            if sid:
                ov = editor.get_overrides()
                if ov:
                    overrides[sid] = ov
        for box, editor in zip(self.base_boxes, self.base_param_editors):
            sid = box.currentData() or ""
            if sid and box.currentText() != "None":
                ov = editor.get_overrides()
                if ov:
                    overrides[sid] = ov
        for box, editor in zip(self.plugin_boxes, self.plugin_param_editors):
            sid = box.currentData() or ""
            if sid and box.currentText() != "None":
                ov = editor.get_overrides()
                if ov:
                    overrides[sid] = ov
        for box, editor in zip(self.mount_boxes, self.mount_param_editors):
            sid = box.currentData() or ""
            if sid and box.currentText() != "None":
                ov = editor.get_overrides()
                if ov:
                    overrides[sid] = ov
        return {
            "hero_name_or_preset": self.name_edit.text().strip(),
            "talent_ids": [box.currentData() or "" for box in self.talent_boxes],
            "base_skill_ids": [box.currentData() or "" for box in self.base_boxes if box.currentText() != "None"],
            "plugin_skill_ids": [box.currentData() or "" for box in self.plugin_boxes if box.currentText() != "None"],
            "mount_skill_ids": [box.currentData() or "" for box in self.mount_boxes if box.currentText() != "None"],
            "skill_overrides": overrides,
        }


class ArmyFrame(QtWidgets.QGroupBox):
    """Inputs for a single army."""

    def __init__(self, index: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(f"Army {index}", parent)
        self.index = index

        self.hero_options = ["None", "Custom"] + sorted(name.capitalize() for name in HERO_PRESETS.keys())

        self.name_edit = QtWidgets.QLineEdit(f"Army {index}")
        self._user_named = False
        self.name_edit.textEdited.connect(lambda _: setattr(self, "_user_named", True))
        self.unit_combo = QtWidgets.QComboBox()
        for u in sorted(Unit.ALLOWED_TYPES):
            self.unit_combo.addItem(u)
        self.unit_combo.currentTextChanged.connect(self._unit_changed)
        self.tier_spin = QtWidgets.QSpinBox()
        self.tier_spin.setRange(min(Unit.ALLOWED_TIERS), max(Unit.ALLOWED_TIERS))
        self.tier_spin.setValue(5)

        self.count_spin = ThousandSepSpinBox()
        self.count_spin.setRange(0, 100000000)
        self.count_spin.setValue(100000)

        self.rally_checkbox = QtWidgets.QCheckBox("Treat as rally army")

        self.atk_edit = QtWidgets.QDoubleSpinBox()
        self.atk_edit.setRange(-10.0, 10.0)
        self.atk_edit.setDecimals(4)
        self.atk_edit.setSingleStep(0.0001)
        self.atk_edit.setValue(0.0)

        self.def_edit = QtWidgets.QDoubleSpinBox()
        self.def_edit.setRange(-10.0, 10.0)
        self.def_edit.setDecimals(4)
        self.def_edit.setSingleStep(0.0001)
        self.def_edit.setValue(0.0)

        self.hp_edit = QtWidgets.QDoubleSpinBox()
        self.hp_edit.setRange(-10.0, 10.0)
        self.hp_edit.setDecimals(4)
        self.hp_edit.setSingleStep(0.0001)
        self.hp_edit.setValue(0.0)

        self.unrevivable_spin = QtWidgets.QDoubleSpinBox()
        self.unrevivable_spin.setRange(0.0, 1.0)
        self.unrevivable_spin.setDecimals(4)
        self.unrevivable_spin.setSingleStep(0.0001)
        self.unrevivable_spin.setValue(0.65)
        self.dynamic_unrevivable_button = QtWidgets.QToolButton()
        self.dynamic_unrevivable_button.setText("Dynamic")
        self.dynamic_unrevivable_button.setCheckable(True)
        self.dynamic_unrevivable_button.setToolTip(
            "Toggle dynamic heavily wounded calculation"
        )
        self.dynamic_unrevivable_button.toggled.connect(
            self._on_dynamic_unrevivable_toggled
        )
        self._on_dynamic_unrevivable_toggled(False)

        self.hero1_combo = QtWidgets.QComboBox()
        self.hero2_combo = QtWidgets.QComboBox()
        for combo in [self.hero1_combo, self.hero2_combo]:
            for opt in self.hero_options:
                combo.addItem(opt)
            combo.setEditable(True)
            completer = QtWidgets.QCompleter(self.hero_options, combo)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            combo.setCompleter(completer)
        self.hero1_combo.currentTextChanged.connect(lambda n: self._hero_selected(1, n))
        self.hero2_combo.currentTextChanged.connect(lambda n: self._hero_selected(2, n))

        self.edit_btn1 = QtWidgets.QPushButton("Edit")
        self.edit_btn2 = QtWidgets.QPushButton("Edit")
        self.edit_btn1.clicked.connect(lambda: self.edit_hero(1))
        self.edit_btn2.clicked.connect(lambda: self.edit_hero(2))

        # Store fully customised hero definitions per slot.  Skill parameter
        # overrides for preset heroes are tracked separately in
        # ``hero_overrides`` so presets can be tweaked without becoming
        # custom entries.
        self.custom_heroes: dict[int, dict] = {1: None, 2: None}
        self._custom_hero_cache: dict[str, dict] = {}
        self.hero_overrides: dict[int, dict] = {1: {}, 2: {}}
        self._hero_override_cache: dict[str, dict] = {}
        self._hero_names: dict[int, str] = {1: "None", 2: "None"}
        # Plugin skills are preserved per slot so switching heroes does not
        # automatically overwrite the player's chosen loadout.
        self._slot_plugin_loadouts: dict[int, list[str] | None] = {1: None, 2: None}
        self._slot_plugin_star_counts: dict[int, list[int]] = {1: [], 2: []}
        self._loading_config = False
        self._peer_frames: list[ArmyFrame] = []

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

        layout.addWidget(QtWidgets.QLabel("Rally army:"), row, 0)
        layout.addWidget(self.rally_checkbox, row, 1)
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
        layout.addWidget(self.dynamic_unrevivable_button, row, 2)
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
        row += 1

        # --- Feature buttons ---
        self.gear_btn = QtWidgets.QPushButton("Gear")
        self.mount_skills_btn = QtWidgets.QPushButton("Mount Skills")
        self.gem_skills_btn = QtWidgets.QPushButton("Jewel Skills")
        self.bonus_stats_btn = QtWidgets.QPushButton("Bonus Stats")

        self._bonus_stats = default_bonus_stats()
        self._mount_skills: dict[int, list[str]] = {1: [], 2: []}
        self._gem_skills: dict[str, str] = {slot: "" for slot, _ in JEWEL_SLOTS}
        self._hero_gear: dict[int, dict[str, str]] = {1: {}, 2: {}}
        self.mount_skills_btn.clicked.connect(self._open_mount_skills_dialog)
        self.gem_skills_btn.clicked.connect(self._open_gem_skills_dialog)
        self.bonus_stats_btn.clicked.connect(self._open_bonus_stats_dialog)

        feature_btn_layout = QtWidgets.QHBoxLayout()
        feature_btn_layout.setSpacing(10)
        for btn in [
            self.gear_btn,
            self.mount_skills_btn,
            self.gem_skills_btn,
            self.bonus_stats_btn,
        ]:
            btn.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            feature_btn_layout.addWidget(btn)
        layout.addLayout(feature_btn_layout, row, 0, 1, 4)
        # Extra row for preview content added externally

        self._update_bonus_stats_button()
        self._update_mount_skills_button()
        self._update_gem_skills_button()
        self._update_gear_button()

        # --- Troop type icon ---
        self.unit_icon = QtWidgets.QLabel()
        self.unit_icon.setFixedSize(92, 92)
        self.unit_icon.setScaledContents(True)

        # --- Hero 1 preview widget ---
        self.hero1_img = StarredImageLabel()
        self.hero1_img.setFixedSize(48, 69)
        self.hero1_plugin_imgs = [StarredImageLabel(), StarredImageLabel()]
        for lbl in self.hero1_plugin_imgs:
            lbl.setFixedSize(56, 69)
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
        self.hero2_img = StarredImageLabel()
        self.hero2_img.setFixedSize(48, 69)
        self.hero2_plugin_imgs = [StarredImageLabel(), StarredImageLabel()]
        for lbl in self.hero2_plugin_imgs:
            lbl.setFixedSize(56, 69)
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

    def set_peer_frames(self, peers: Iterable["ArmyFrame"]) -> None:
        self._peer_frames = [p for p in peers if p is not self]

    def _cache_custom_hero(self, cfg: dict | None) -> None:
        if not cfg:
            return
        name = cfg.get("hero_name_or_preset")
        if not name:
            return
        self._custom_hero_cache[name] = copy.deepcopy(cfg)

    def _cache_overrides(self, hero_name: str, overrides: dict | None) -> None:
        if not hero_name:
            return
        if overrides:
            self._hero_override_cache[hero_name] = copy.deepcopy(overrides)
        elif hero_name in self._hero_override_cache:
            self._hero_override_cache.pop(hero_name, None)

    def _resolve_auto_name_conflict(self, candidate: str) -> str:
        peer_names = {peer.name_edit.text() for peer in self._peer_frames if peer}
        if candidate not in peer_names:
            return candidate
        base = candidate
        suffix = 2
        while True:
            unique = f"{base} ({suffix})"
            if unique not in peer_names:
                return unique
            suffix += 1

    def _clear_plugin_loadout(self, slot: int) -> None:
        self._slot_plugin_loadouts[slot] = None
        self._slot_plugin_star_counts[slot] = []
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        for lbl in plugin_labels:
            lbl.set_image(None)
            lbl.setToolTip("")
            setattr(lbl, "skill_id", "")

    def _set_plugin_loadout(
        self,
        slot: int,
        plugin_ids: Iterable[str] | None,
        star_counts: Iterable[int] | None = None,
        *,
        update_ui: bool = True,
    ) -> None:
        cleaned_ids: list[str] = []
        if plugin_ids:
            for sid in plugin_ids:
                if isinstance(sid, str) and sid:
                    cleaned_ids.append(sid)
        self._slot_plugin_loadouts[slot] = cleaned_ids

        counts: list[int] = []
        if star_counts:
            for idx, count in enumerate(star_counts):
                if idx >= len(cleaned_ids):
                    break
                try:
                    counts.append(int(count))
                except Exception:
                    continue
        self._slot_plugin_star_counts[slot] = counts

        if update_ui:
            self._render_plugin_loadout(slot)

    def _render_plugin_loadout(self, slot: int) -> None:
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        for lbl in plugin_labels:
            lbl.set_image(None)
            lbl.setToolTip("")
            setattr(lbl, "skill_id", "")

        plugin_ids = self._slot_plugin_loadouts.get(slot) or []
        star_counts = self._slot_plugin_star_counts.get(slot) or []
        if not plugin_ids:
            self._slot_plugin_star_counts[slot] = []
            return

        updated_counts: list[int] = []
        for idx, sid in enumerate(plugin_ids):
            if idx >= len(plugin_labels):
                break
            lbl = plugin_labels[idx]
            skill_def = SKILL_REGISTRY_GLOBAL.get(sid)
            if skill_def:
                img_name = skill_def["name"].replace("'", "").replace(" ", "-") + ".png"
                skill_img_path = os.path.join(
                    os.path.dirname(__file__), "Plugin Skill Images", img_name
                )
                lbl.setToolTip(skill_def.get("name", sid))
                if os.path.exists(skill_img_path):
                    lbl.set_image(skill_img_path)
                    lbl.setText("")
                else:
                    lbl.setText(skill_def.get("name", sid))
                    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            else:
                lbl.setText(sid)
                lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            setattr(lbl, "skill_id", sid)
            if star_counts and idx < len(star_counts):
                try:
                    lbl.set_star_count(int(star_counts[idx]))
                except Exception:
                    lbl.set_star_count(lbl.max_stars)
            else:
                lbl.set_star_count(lbl.max_stars)
            try:
                updated_counts.append(int(lbl.star_count))
            except Exception:
                updated_counts.append(int(getattr(lbl, "max_stars", 6)))

        self._slot_plugin_star_counts[slot] = updated_counts

    def _capture_plugin_state(self, slot: int) -> None:
        loadout = self._slot_plugin_loadouts.get(slot)
        if loadout is None:
            return
        if not loadout:
            self._slot_plugin_star_counts[slot] = []
            return
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        stars: list[int] = []
        for idx, sid in enumerate(loadout):
            if idx >= len(plugin_labels):
                break
            lbl = plugin_labels[idx]
            if getattr(lbl, "_orig_image", None) is None and not lbl.text():
                continue
            try:
                stars.append(int(lbl.star_count))
            except Exception:
                stars.append(int(getattr(lbl, "max_stars", 6)))
        self._slot_plugin_star_counts[slot] = stars

    def edit_hero(self, slot: int) -> None:
        """Open the hero editor and persist changes.

        Skill parameter overrides are stored separately so that preset heroes
        can be tweaked without converting them into full custom entries.
        """
        current_cfg = self.custom_heroes.get(slot)
        hero_name = self.hero1_combo.currentText() if slot == 1 else self.hero2_combo.currentText()
        if current_cfg is None and hero_name not in {"None", "Custom"}:
            cached_cfg = self._custom_hero_cache.get(hero_name)
            if cached_cfg:
                current_cfg = copy.deepcopy(cached_cfg)
        if current_cfg is None:
            preset = HERO_PRESETS.get(hero_name.lower())
            if preset:
                current_cfg = {
                    "hero_name_or_preset": hero_name,
                    "talent_ids": preset.get("talents", []),
                    "base_skill_ids": preset.get("base_skills", []),
                    "plugin_skill_ids": preset.get("plugin_skills", []),
                }
        slot_plugins = self._slot_plugin_loadouts.get(slot)
        if slot_plugins is not None:
            current_cfg = dict(current_cfg or {"hero_name_or_preset": hero_name})
            current_cfg["plugin_skill_ids"] = list(slot_plugins)
        slot_mounts = self._mount_skills.get(slot)
        if slot_mounts is not None:
            current_cfg = dict(current_cfg or {"hero_name_or_preset": hero_name})
            current_cfg["mount_skill_ids"] = list(slot_mounts)
        overrides = self.hero_overrides.get(slot)
        if overrides:
            current_cfg = dict(current_cfg or {"hero_name_or_preset": hero_name})
            current_cfg["skill_overrides"] = overrides

        dlg = HeroEditDialog(current_cfg, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dlg.result_config()
            if cfg:
                overrides = cfg.pop("skill_overrides", {})
                self.hero_overrides[slot] = overrides
                name = cfg["hero_name_or_preset"]
                self._cache_overrides(name, overrides)
                self._set_plugin_loadout(slot, cfg.get("plugin_skill_ids", []), update_ui=False)
                mount_skills = cfg.get("mount_skill_ids")
                if mount_skills is not None:
                    self._set_mount_skills({slot: mount_skills})
                preset = HERO_PRESETS.get(name.lower())
                if (
                    preset
                    and preset.get("talents", []) == cfg.get("talent_ids")
                    and preset.get("base_skills", []) == cfg.get("base_skill_ids")
                    and preset.get("plugin_skills", []) == cfg.get("plugin_skill_ids")
                ):
                    self.custom_heroes[slot] = None
                    self._custom_hero_cache.pop(name, None)
                else:
                    cfg_copy = copy.deepcopy(cfg)
                    self.custom_heroes[slot] = cfg_copy
                    self._cache_custom_hero(cfg_copy)
                    self._add_custom_option(name)
                # Update selection without losing overrides
                self._hero_names[slot] = name
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

        prev_name = self._hero_names.get(slot)
        prev_cfg = self.custom_heroes.get(slot)
        changed = prev_name != name
        if changed and prev_cfg and prev_cfg.get("hero_name_or_preset"):
            self._cache_custom_hero(prev_cfg)
        if changed and prev_name not in {None, "", "None", "Custom"}:
            prev_overrides = self.hero_overrides.get(slot)
            if prev_overrides:
                self._cache_overrides(prev_name, prev_overrides)
            else:
                self._cache_overrides(prev_name, None)
        if changed:
            if name not in {"None", "Custom"}:
                overrides = copy.deepcopy(self._hero_override_cache.get(name, {}))
            else:
                overrides = {}
            self.hero_overrides[slot] = overrides
            self._user_named = False
        cfg = self.custom_heroes.get(slot)
        if not cfg or cfg.get("hero_name_or_preset") != name:
            if name not in {"None", "Custom"}:
                cached_cfg = self._custom_hero_cache.get(name)
                if cached_cfg:
                    cfg = copy.deepcopy(cached_cfg)
                    self.custom_heroes[slot] = cfg
                else:
                    self.custom_heroes[slot] = None
                    cfg = None
            else:
                self.custom_heroes[slot] = None
                cfg = None
        self._hero_names[slot] = name

        if name in {"None", ""} and self._hero_gear.get(slot):
            self._hero_gear[slot] = {}
        self._update_gear_button()
        if name in {"None", ""}:
            self._mount_skills[slot] = []
            self._update_mount_skills_button()

        img_label = self.hero1_img if slot == 1 else self.hero2_img
        img_label.set_image(None)
        img_label.setToolTip(name if name not in {"None", "Custom"} else "")
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        if not self._loading_config:
            self._capture_plugin_state(slot)
        for lbl in plugin_labels:
            lbl.setToolTip("")
        if name not in {"None", "Custom"}:
            img_path = os.path.join(os.path.dirname(__file__), "Hero Images", f"{name.capitalize()}.png")
            if os.path.exists(img_path):
                img_label.set_image(img_path)
                img_label.setText("")
            else:
                img_label.setText(name)
                img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            loadout = self._slot_plugin_loadouts.get(slot)
            if loadout is None:
                if cfg and cfg.get("hero_name_or_preset") == name:
                    plugin_ids = cfg.get("plugin_skill_ids", [])
                    plugin_counts = cfg.get("plugin_star_counts") if cfg else None
                    self._set_plugin_loadout(slot, plugin_ids, plugin_counts, update_ui=False)
                else:
                    preset = HERO_PRESETS.get(name.lower())
                    plugin_ids = preset.get("plugin_skills", []) if preset else []
                    self._set_plugin_loadout(slot, plugin_ids, update_ui=False)
                loadout = self._slot_plugin_loadouts.get(slot)
            self._render_plugin_loadout(slot)
        else:
            self._clear_plugin_loadout(slot)
        self._update_mount_skills_button()
        self._update_name_if_auto()

    def _update_name_if_auto(self) -> None:
        if self._user_named:
            return
        hero1 = self.hero1_combo.currentText()
        hero2 = self.hero2_combo.currentText()
        if hero1 in {"", "None"} and hero2 in {"", "None"}:
            new_name = f"Army {self.index}"
        else:
            if hero1 in {"", "None"}:
                hero1 = "None"
            if hero2 in {"", "None"}:
                hero2 = "None"
            new_name = f"{hero1}/{hero2}"
        unique_name = self._resolve_auto_name_conflict(new_name)
        if self.name_edit.text() != unique_name:
            self.name_edit.setText(unique_name)

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

    def _on_dynamic_unrevivable_toggled(self, checked: bool) -> None:
        self.unrevivable_spin.setEnabled(not checked)
        if checked:
            self.unrevivable_spin.setToolTip(
                "Static heavily wounded ratio is ignored while dynamic mode is active."
            )
        else:
            self.unrevivable_spin.setToolTip("")

    def populate_from_config(self, cfg: dict) -> None:
        self._loading_config = True
        try:
            self._user_named = bool(cfg.get("army_name"))
            self.name_edit.setText(cfg.get("army_name", f"Army {self.index}"))
            self.unit_combo.setCurrentText(cfg.get("unit_type", "pikemen"))
            self._unit_changed(self.unit_combo.currentText())
            self.tier_spin.setValue(int(cfg.get("tier", 5)))
            self.count_spin.setValue(int(cfg.get("count", 100000)))
            self.rally_checkbox.setChecked(bool(cfg.get("is_rally", False)))
            self.atk_edit.setValue(float(cfg.get("atk_mod", 0)))
            self.def_edit.setValue(float(cfg.get("def_mod", 0)))
            self.hp_edit.setValue(float(cfg.get("hp_mod", 0)))

            self.unrevivable_spin.setValue(float(cfg.get("unrevivable_ratio", 0.65)))
            self.dynamic_unrevivable_button.setChecked(
                bool(cfg.get("use_dynamic_unrevivable_ratio", False))
            )

            hero_combos = [self.hero1_combo, self.hero2_combo]
            for idx, combo in enumerate(hero_combos, start=1):
                combo.setCurrentText("None")
                self.custom_heroes[idx] = None
                self.hero_overrides[idx] = {}
                self._hero_names[idx] = "None"
                self._clear_plugin_loadout(idx)
            self._custom_hero_cache.clear()
            self._hero_override_cache.clear()
            self._hero_gear = {1: {}, 2: {}}
            self._update_gear_button()
            gear_map: dict[int, dict[str, str]] = {1: {}, 2: {}}
            mount_map: dict[int, list[str]] = {1: [], 2: []}
            for idx, hero_cfg in enumerate(cfg.get("heroes", []), start=1):
                if idx > 2:
                    break
                name = hero_cfg.get("hero_name_or_preset", "")
                overrides = hero_cfg.get("skill_overrides", {})
                preset = HERO_PRESETS.get(name.lower())
                if (
                    preset
                    and preset.get("talents") == hero_cfg.get("talent_ids")
                    and preset.get("base_skills") == hero_cfg.get("base_skill_ids")
                    and preset.get("plugin_skills") == hero_cfg.get("plugin_skill_ids")
                ):
                    hero_name_display = name.capitalize()
                    overrides_copy = copy.deepcopy(overrides) if overrides else {}
                    self.hero_overrides[idx] = overrides_copy
                    self._cache_overrides(hero_name_display, overrides_copy)
                else:
                    hero_name_display = name
                    cfg_copy = {k: v for k, v in hero_cfg.items() if k != "skill_overrides"}
                    if hero_name_display and cfg_copy.get("hero_name_or_preset") != hero_name_display:
                        cfg_copy["hero_name_or_preset"] = hero_name_display
                    cfg_copy = copy.deepcopy(cfg_copy)
                    self.custom_heroes[idx] = cfg_copy
                    self._cache_custom_hero(cfg_copy)
                    overrides_copy = copy.deepcopy(overrides) if overrides else {}
                    self.hero_overrides[idx] = overrides_copy
                    self._cache_overrides(hero_name_display, overrides_copy)
                    self._add_custom_option(name)
                combo = hero_combos[idx - 1]
                # ``setCurrentText`` emits ``currentTextChanged`` which would in
                # turn invoke ``_hero_selected`` and clear any overrides.  Block
                # signals while populating and explicitly update the info labels
                # afterwards.
                self._hero_names[idx] = hero_name_display
                block = combo.blockSignals(True)
                combo.setCurrentText(hero_name_display)
                combo.blockSignals(block)

                plugin_ids_cfg = hero_cfg.get("plugin_skill_ids")
                plugin_counts_cfg = hero_cfg.get("plugin_star_counts")
                if plugin_ids_cfg is not None:
                    self._set_plugin_loadout(
                        idx, plugin_ids_cfg, plugin_counts_cfg, update_ui=False
                    )

                self._hero_selected(idx, hero_name_display)

                mount_ids_cfg = hero_cfg.get("mount_skill_ids")
                if isinstance(mount_ids_cfg, (list, tuple)):
                    mount_map[idx] = [
                        sid for sid in mount_ids_cfg if isinstance(sid, str) and sid.strip()
                    ]

                raw_gear_cfg: dict[str, Any] = {}
                if isinstance(hero_cfg, dict):
                    if isinstance(hero_cfg.get("gear_ids"), dict):
                        raw_gear_cfg = dict(hero_cfg.get("gear_ids", {}))
                    elif isinstance(hero_cfg.get("gear"), dict):
                        raw_gear_cfg = dict(hero_cfg.get("gear", {}))
                normalized_slots: dict[str, str] = {}
                for slot_key, raw_value in raw_gear_cfg.items():
                    slot_name = normalize_gear_slot(slot_key)
                    if not slot_name:
                        continue
                    gear_def = resolve_gear(raw_value)
                    if not gear_def or gear_def.slot != slot_name:
                        continue
                    normalized_slots[slot_name] = gear_def.id
                if normalized_slots:
                    gear_map[idx] = normalized_slots
            self._set_gear_config(gear_map)
            self._set_mount_skills(mount_map)

            for idx, combo in enumerate(hero_combos, start=1):
                self._hero_selected(idx, combo.currentText())

            self._restore_star_counts(cfg.get("heroes"))

            self._set_gem_skills(cfg.get("gem_skills"))
            self._set_bonus_stats(cfg.get("bonus_stats"))
            for idx in (1, 2):
                self._capture_plugin_state(idx)
        finally:
            self._loading_config = False

    def build_config(self) -> dict:
        heroes_cfg = []
        for idx, combo in enumerate([self.hero1_combo, self.hero2_combo], start=1):
            hero_name = combo.currentText()
            if hero_name and hero_name not in {"None", "Custom"}:
                overrides = self.hero_overrides.get(idx) or {}
                custom_cfg = self.custom_heroes.get(idx)
                if custom_cfg and custom_cfg.get("hero_name_or_preset") == hero_name:
                    cfg = custom_cfg.copy()
                else:
                    preset = HERO_PRESETS.get(hero_name.lower())
                    if not preset:
                        continue
                    cfg = {
                        "hero_name_or_preset": hero_name,
                        "talent_ids": preset.get("talents", []),
                        "base_skill_ids": preset.get("base_skills", []),
                        "plugin_skill_ids": preset.get("plugin_skills", []),
                    }
                if overrides:
                    # Overrides tweak preset talents/skills without requiring a
                    # separate custom hero entry.
                    cfg["skill_overrides"] = overrides

                slot_loadout = self._slot_plugin_loadouts.get(idx)
                if slot_loadout is not None:
                    cfg["plugin_skill_ids"] = list(slot_loadout)

                hero_label = self.hero1_img if idx == 1 else self.hero2_img
                if getattr(hero_label, "_orig_image", None) is not None:
                    try:
                        star_count = int(hero_label.star_count)
                    except Exception:
                        star_count = int(getattr(hero_label, "max_stars", 6))
                    max_stars = max(1, int(getattr(hero_label, "max_stars", 6)))
                    if star_count < max_stars:
                        cfg["star_count"] = star_count

                plugin_labels = (
                    self.hero1_plugin_imgs if idx == 1 else self.hero2_plugin_imgs
                )
                plugin_ids = cfg.get("plugin_skill_ids", []) or []
                plugin_counts: list[int] = []
                any_custom_plugin = False
                for plugin_idx, sid in enumerate(plugin_ids):
                    if plugin_idx >= len(plugin_labels):
                        break
                    lbl = plugin_labels[plugin_idx]
                    max_stars = max(1, int(getattr(lbl, "max_stars", 6)))
                    try:
                        count = int(getattr(lbl, "star_count", max_stars))
                    except Exception:
                        count = max_stars
                    plugin_counts.append(count)
                    if getattr(lbl, "_orig_image", None) is not None and count < max_stars:
                        any_custom_plugin = True
                if any_custom_plugin and plugin_counts:
                    cfg["plugin_star_counts"] = plugin_counts

                mount_skills = [sid for sid in self._mount_skills.get(idx, []) if sid]
                if mount_skills:
                    cfg["mount_skill_ids"] = mount_skills

                gear_selection = self._hero_gear.get(idx, {})
                if gear_selection:
                    cfg["gear_ids"] = dict(gear_selection)
                heroes_cfg.append(cfg)

        config = {
            "army_name": self.name_edit.text() or f"Army {self.index}",
            "unit_type": self.unit_combo.currentText(),
            "tier": int(self.tier_spin.value()),
            "count": int(self.count_spin.value()),
            "is_rally": self.rally_checkbox.isChecked(),
            "atk_mod": float(self.atk_edit.value()),
            "def_mod": float(self.def_edit.value()),
            "hp_mod": float(self.hp_edit.value()),
            "unrevivable_ratio": float(self.unrevivable_spin.value()),
            "use_dynamic_unrevivable_ratio": self.dynamic_unrevivable_button.isChecked(),
            "heroes": heroes_cfg,
        }

        bonus_stats_serialized = serialize_bonus_stats(self._bonus_stats)
        if bonus_stats_serialized:
            config["bonus_stats"] = bonus_stats_serialized

        gem_skills_serialized = {
            slot: sid for slot, sid in self._gem_skills.items() if sid
        }
        if gem_skills_serialized:
            config["gem_skills"] = gem_skills_serialized

        return config

    def _restore_star_counts(self, heroes_cfg: list[dict] | None) -> None:
        if not heroes_cfg:
            return
        hero_labels = [self.hero1_img, self.hero2_img]
        plugin_label_sets = [self.hero1_plugin_imgs, self.hero2_plugin_imgs]
        for idx, hero_cfg in enumerate(heroes_cfg):
            if idx >= len(hero_labels):
                break
            label = hero_labels[idx]
            if getattr(label, "_orig_image", None) is not None:
                star_value = hero_cfg.get("star_count")
                if star_value is not None:
                    try:
                        label.set_star_count(int(star_value))
                    except Exception:
                        label.set_star_count(label.max_stars)
            plugin_counts = hero_cfg.get("plugin_star_counts")
            if not isinstance(plugin_counts, list):
                continue
            plugin_labels = plugin_label_sets[idx]
            for plugin_idx, count in enumerate(plugin_counts):
                if plugin_idx >= len(plugin_labels):
                    break
                lbl = plugin_labels[plugin_idx]
                if getattr(lbl, "_orig_image", None) is None:
                    continue
                if count is None:
                    lbl.set_star_count(lbl.max_stars)
                else:
                    try:
                        lbl.set_star_count(int(count))
                    except Exception:
                        lbl.set_star_count(lbl.max_stars)

    def _open_bonus_stats_dialog(self) -> None:
        dlg = BonusStatsDialog(self._bonus_stats, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._set_bonus_stats(dlg.result())

    def _set_bonus_stats(self, stats: dict[str, Any] | None) -> None:
        self._bonus_stats = merge_bonus_stats(default_bonus_stats(), stats or {})
        self._update_bonus_stats_button()

    def _open_mount_skills_dialog(self) -> None:
        hero_names = {1: self.hero1_combo.currentText(), 2: self.hero2_combo.currentText()}
        dlg = MountSkillsDialog(self._mount_skills, hero_names, self.hero_overrides, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            mount_skills, mount_overrides = dlg.result()
            self._set_mount_skills(mount_skills)
            self._apply_mount_overrides(mount_skills, mount_overrides)

    def _set_mount_skills(self, mount_skills: dict[int, list[str]] | None) -> None:
        normalized: dict[int, list[str]] = {
            1: list(self._mount_skills.get(1, [])),
            2: list(self._mount_skills.get(2, [])),
        }
        if mount_skills:
            for hero_idx, skills in mount_skills.items():
                if hero_idx not in normalized or not isinstance(skills, (list, tuple)):
                    continue
                cleaned: list[str] = []
                for sid in skills:
                    if not isinstance(sid, str):
                        continue
                    trimmed = sid.strip()
                    if not trimmed:
                        continue
                    cleaned.append(trimmed)
                    if len(cleaned) >= 2:
                        break
                normalized[hero_idx] = cleaned
        self._mount_skills = normalized
        self._update_mount_skills_button()

    def _apply_mount_overrides(
        self,
        mount_skills: dict[int, list[str]],
        overrides: dict[int, dict[str, dict]],
    ) -> None:
        for slot in (1, 2):
            current_overrides = self.hero_overrides.get(slot) or {}
            merged: dict[str, dict] = {
                sid: ov for sid, ov in current_overrides.items() if not _is_mount_skill(sid)
            }
            selected_skills = mount_skills.get(slot, []) if isinstance(mount_skills, dict) else []
            slot_overrides = overrides.get(slot, {}) if isinstance(overrides, dict) else {}
            for sid in selected_skills:
                ov = slot_overrides.get(sid) or current_overrides.get(sid)
                if ov:
                    merged[sid] = ov
            self.hero_overrides[slot] = merged

    def _update_mount_skills_button(self) -> None:
        if not hasattr(self, "mount_skills_btn"):
            return
        count, summary = self._mount_skills_summary()
        if count:
            self.mount_skills_btn.setText(f"Mount Skills ({count})")
            self.mount_skills_btn.setToolTip(summary)
        else:
            self.mount_skills_btn.setText("Mount Skills")
            self.mount_skills_btn.setToolTip("No mount skills selected.")

    def _mount_skills_summary(self) -> tuple[int, str]:
        entries: list[str] = []
        total = 0
        for hero_idx in (1, 2):
            skills = self._mount_skills.get(hero_idx, [])
            if not skills:
                continue
            names: list[str] = []
            for sid in skills:
                skill_def = SKILL_REGISTRY_GLOBAL.get(sid)
                names.append(skill_def.get("name", sid) if skill_def else sid)
            hero_name = self._hero_names.get(hero_idx, f"Hero {hero_idx}") or f"Hero {hero_idx}"
            entries.append(f"{hero_name}: {', '.join(names)}")
            total += len(names)
        if not entries:
            return 0, "No mount skills selected."
        return total, "\n".join(entries)

    def _update_bonus_stats_button(self) -> None:
        count, summary = self._bonus_stats_summary()
        if count:
            self.bonus_stats_btn.setText(f"Bonus Stats ({count})")
            self.bonus_stats_btn.setToolTip(summary)
        else:
            self.bonus_stats_btn.setText("Bonus Stats")
            self.bonus_stats_btn.setToolTip("No manual bonus stats configured.")

    def _bonus_stats_summary(self) -> tuple[int, str]:
        entries = []

        def fmt_percent(value: float, invert: bool = False) -> str:
            percent = -value * 100 if invert else value * 100
            return f"{percent:+.1f}%"

        for item in iter_bonus_stat_entries(self._bonus_stats):
            entries.append(f"{item['label']}: {fmt_percent(item['value'], item['invert'])}")

        return len(entries), "\n".join(entries)

    def _open_gem_skills_dialog(self) -> None:
        dlg = JewelSkillsDialog(self._gem_skills, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._set_gem_skills(dlg.result())

    def _set_gem_skills(self, gem_skills: dict[str, Any] | None) -> None:
        normalized = {slot: "" for slot, _ in JEWEL_SLOTS}
        if gem_skills:
            for slot, sid in gem_skills.items():
                if slot not in normalized:
                    continue
                normalized_id = normalize_gem_skill_id(sid)
                normalized[slot] = normalized_id if normalized_id else ""
        self._gem_skills = normalized
        self._update_gem_skills_button()

    def _update_gem_skills_button(self) -> None:
        count, summary = self._gem_skills_summary()
        if count:
            self.gem_skills_btn.setText(f"Jewel Skills ({count})")
            self.gem_skills_btn.setToolTip(summary)
        else:
            self.gem_skills_btn.setText("Jewel Skills")
            self.gem_skills_btn.setToolTip("No jewel skills selected.")

    def _gem_skills_summary(self) -> tuple[int, str]:
        entries: list[str] = []
        count = 0
        for slot_key, slot_label in JEWEL_SLOTS:
            sid = self._gem_skills.get(slot_key, "")
            if not sid:
                continue
            count += 1
            skill_def = SKILL_REGISTRY_GLOBAL.get(sid)
            if skill_def:
                name = skill_def.get("name", sid)
                rarity = skill_def.get("config", {}).get("rarity")
                if rarity and rarity not in name:
                    entries.append(f"{slot_label}: {name} ({rarity})")
                else:
                    entries.append(f"{slot_label}: {name}")
            else:
                entries.append(f"{slot_label}: {sid}")
        if not entries:
            return 0, "No jewel skills selected."
        return count, "\n".join(entries)

    def get_gear_config(self) -> dict[int, dict[str, str]]:
        return {idx: dict(slots) for idx, slots in self._hero_gear.items() if slots}

    def set_gear_config(self, gear_config: dict[int, dict[str, str]] | None) -> None:
        self._set_gear_config(gear_config)

    def _set_gear_config(self, gear_config: dict[int, dict[str, str]] | None) -> None:
        normalized: dict[int, dict[str, str]] = {1: {}, 2: {}}
        if gear_config:
            for hero_idx, gear_map in gear_config.items():
                if hero_idx not in normalized or not isinstance(gear_map, dict):
                    continue
                for slot_key, raw_value in gear_map.items():
                    slot_name = normalize_gear_slot(slot_key)
                    if not slot_name:
                        continue
                    gear_def = resolve_gear(raw_value)
                    if not gear_def or gear_def.slot != slot_name:
                        continue
                    normalized[hero_idx][slot_name] = gear_def.id
        self._hero_gear = normalized
        self._update_gear_button()

    def _update_gear_button(self) -> None:
        if not hasattr(self, "gear_btn"):
            return
        count, summary = self._gear_summary()
        if count:
            self.gear_btn.setText(f"Gear ({count})")
            self.gear_btn.setToolTip(summary)
        else:
            self.gear_btn.setText("Gear")
            self.gear_btn.setToolTip("No gear equipped.")

    def _gear_summary(self) -> tuple[int, str]:
        entries: list[str] = []
        total = 0
        for hero_idx in (1, 2):
            gear_map = self._hero_gear.get(hero_idx, {})
            if not gear_map:
                continue
            hero_name = self._hero_names.get(hero_idx, f"Hero {hero_idx}")
            hero_display = hero_name if hero_name not in {"", "None"} else f"Hero {hero_idx}"
            parts: list[str] = []
            for slot_key, slot_label in GEAR_SLOT_ORDER:
                gear_id = gear_map.get(slot_key)
                if not gear_id:
                    continue
                gear_def = GEAR_REGISTRY.get(gear_id) or resolve_gear(gear_id)
                if not gear_def:
                    continue
                total += 1
                parts.append(f"{slot_label}: {gear_def.name} ({gear_def.rarity})")
            if parts:
                entries.append(f"{hero_display}: {', '.join(parts)}")
        if not entries:
            return 0, "No gear equipped."
        return total, "\n".join(entries)


class ArmySetupDialog(QtWidgets.QDialog):
    """Dialog wrapping :class:`ArmyFrame` for defining an army.

    The dialog reuses the existing 1v1 configuration form and augments it with a
    simple team selector so the returned configuration contains all information
    required for :class:`BattlefieldEngine`.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Army Setup")
        layout = QtWidgets.QVBoxLayout(self)

        self.frame = ArmyFrame(1)
        layout.addWidget(self.frame)

        team_row = QtWidgets.QHBoxLayout()
        team_row.addWidget(QtWidgets.QLabel("Team:"))
        self.team_combo = QtWidgets.QComboBox()
        self.team_combo.setEditable(True)
        self.team_combo.addItems(["red", "blue"])
        team_row.addWidget(self.team_combo)
        layout.addLayout(team_row)

        speed_row = QtWidgets.QHBoxLayout()
        speed_row.addWidget(QtWidgets.QLabel("Speed:"))
        self.speed_spin = QtWidgets.QDoubleSpinBox()
        # Allow armies to move significantly faster when desired.  The original
        # implementation capped the configurable movement speed at ``10`` which
        # proved too limiting when experimenting with battlefield scenarios.
        # Increasing the upper bound to ``100`` lets users rapidly reposition
        # armies across the map while still permitting fine grained slow
        # movement via the single step value.
        self.speed_spin.setRange(0.0, 100.0)
        self.speed_spin.setDecimals(4)
        self.speed_spin.setSingleStep(0.0001)
        self.speed_spin.setValue(50.0)
        speed_row.addWidget(self.speed_spin)
        layout.addLayout(speed_row)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.save_army_btn = buttons.addButton(
            "Save Army", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole
        )
        self.load_army_btn = buttons.addButton(
            "Load Army", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole
        )
        self.save_army_btn.clicked.connect(self._save_army)
        self.load_army_btn.clicked.connect(self._load_army)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_army(self) -> None:
        cfg = self.get_config()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Army", "", "JSON Files (*.json)"
        )
        if file_path:
            save_army_to_file(cfg, file_path)

    def _load_army(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Army", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        cfg = load_army_from_file(file_path)
        if not cfg:
            return
        self.frame.populate_from_config(cfg)
        self.team_combo.setCurrentText(cfg.get("team", "red"))
        self.speed_spin.setValue(float(cfg.get("speed", 50.0)))

    def get_config(self) -> dict:
        cfg = self.frame.build_config()
        cfg["team"] = self.team_combo.currentText()
        cfg["speed"] = float(self.speed_spin.value())
        return cfg


class ArmyIcon(QtWidgets.QGraphicsItem):
    """Graphics item representing an army with portraits, health and rage bars."""

    def __init__(
        self,
        main_image: str,
        secondary_image: str | None = None,
        health_ratio: float = 1.0,
        *,
        army_name: str | None = None,
        team: str | None = None,
        max_size: int = 64,
        on_drop: Callable[[str, QtCore.QPointF], None] | None = None,
        on_double_click: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        # Scale the main portrait so that extremely large source images do not
        # overwhelm the battlefield grid.  ``max_size`` refers to the maximum
        # width/height of the portrait itself; the health bar is drawn outside
        # of this area.
        self.main_pix = QtGui.QPixmap(main_image).scaled(
            max_size,
            max_size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.sec_pix: QtGui.QPixmap | None = None
        if secondary_image:
            sec = QtGui.QPixmap(secondary_image)
            self.sec_pix = sec.scaled(
                self.main_pix.width() // 2,
                self.main_pix.height() // 2,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        self.health_ratio = max(0.0, min(1.0, health_ratio))
        self.army_name = army_name
        self.team = team
        self._on_drop = on_drop
        self._on_double_click = on_double_click
        self._drag_offset = QtCore.QPointF()
        self._dragging = False
        self.rage_ratio = 0.0
        if self._on_drop is not None or self._on_double_click is not None:
            self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)

    def boundingRect(self) -> QtCore.QRectF:  # type: ignore[override]
        """Return the bounding rectangle including health and rage bars."""

        # Extra margins for the vertical health bar on the left and the
        # horizontal rage bar on top.
        side_extra = 6  # health bar width (4px) + 2px spacing
        top_extra = 6  # rage bar height (4px) + 2px spacing
        width = self.main_pix.width() + side_extra
        height = self.main_pix.height() + top_extra
        return QtCore.QRectF(-side_extra, -top_extra, width, height)

    def paint(  # type: ignore[override]
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        painter.drawPixmap(0, 0, self.main_pix)
        if self.sec_pix is not None:
            x = self.main_pix.width() - self.sec_pix.width()
            y = self.main_pix.height() - self.sec_pix.height()
            painter.drawPixmap(x, y, self.sec_pix)

        # Draw horizontal rage bar above the main portrait
        rage_bar_height = 4
        rage_bar_y = -rage_bar_height - 1  # 1px gap above portrait
        rage_width = self.main_pix.width()
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0)))
        rage_filled = int(rage_width * self.rage_ratio)
        painter.drawRect(0, rage_bar_y, rage_filled, rage_bar_height)

        # Draw the vertical health bar to the *left* of the main image.  The
        # bounding rect has been shifted to expose a 6px wide strip on the left
        # which we can use for the bar and a 1px gap.
        bar_width = 4
        bar_x = -bar_width - 1  # 1px gap between bar and portrait
        bar_height = self.main_pix.height()
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        painter.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))
        filled = int(bar_height * self.health_ratio)
        painter.drawRect(bar_x, bar_height - filled, bar_width, filled)

    def set_health(self, ratio: float) -> None:
        self.health_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_rage(self, ratio: float) -> None:
        self.rage_ratio = max(0.0, min(1.0, ratio))
        self.update()

    # ------------------------------------------------------------------
    # Drag and drop support
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        if self._on_drop is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.pos()
            self.setZValue(10)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        if self._dragging:
            self.setPos(event.scenePos() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        if self._dragging:
            self.setZValue(0)
            self._dragging = False
            if self._on_drop is not None:
                self._on_drop(self.army_name or "", event.scenePos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:  # type: ignore[override]
        if (
            self._on_double_click is not None
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            self._on_double_click(self.army_name or "")
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class SlotItem(QtWidgets.QGraphicsEllipseItem):
    """Clickable marker representing a deployment slot."""

    def __init__(
        self,
        team: str,
        index: int,
        radius: float,
        on_click: Callable[[str, int], None],
        cell_w: float,
        cell_h: float,
    ) -> None:
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.team = team
        self.index = index
        self._on_click = on_click
        self._cell_w = cell_w
        self._cell_h = cell_h
        color = QtGui.QColor(255, 0, 0) if team == "team1" else QtGui.QColor(0, 255, 0)
        pen = QtGui.QPen(color)
        pen.setWidth(2)
        self.setPen(pen)
        self.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.transparent))
        self.setZValue(-1)  # Above background but below army icons
        self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:  # type: ignore[override]
        # Ignore double clicks while movable to avoid opening slot dialog
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and not self.flags()
            & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        ):
            self._on_click(self.team, self.index)
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Drag support for position layout editing
    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        if self.flags() & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
            self.snap_to_grid()

    def snap_to_grid(self) -> None:
        """Snap the item to the nearest grid cell."""
        # Increase snapping granularity by allowing half-cell steps.  This
        # effectively provides four snap points per original grid square,
        # letting users fine tune formation layouts with greater precision.
        step_x = self._cell_w / 2.0
        step_y = self._cell_h / 2.0
        x = round(self.pos().x() / step_x) * step_x
        y = round(self.pos().y() / step_y) * step_y
        self.setPos(x, y)


class BattlefieldTab(QtWidgets.QWidget):
    """Tab showing a battlefield map with army controls."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        controls = QtWidgets.QHBoxLayout()
        self.add_army_btn = QtWidgets.QPushButton("Add Army")
        self.load_army_btn = QtWidgets.QPushButton("Load Army")
        self.refresh_btn = QtWidgets.QPushButton("Refresh Battlefield")
        for btn in (
            self.add_army_btn,
            self.load_army_btn,
            self.refresh_btn,
        ):
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.view.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Use a background image for the battlefield so that the navigation
        # mesh aligns perfectly with it.  Fall back to a default size if the
        # image is unavailable.
        bg_path = os.path.join(
            os.path.dirname(__file__), "Icons", "BattlefieldBackground.png"
        )
        self._background = QtGui.QPixmap(bg_path)
        if not self._background.isNull():
            self.view.setSceneRect(
                0, 0, self._background.width(), self._background.height()
            )
        else:  # pragma: no cover - background image may be missing in tests
            self.view.setSceneRect(0, 0, 800, 600)
        layout.addWidget(self.view, 1)

        # ------------------------------------------------------------------
        # Navigation mesh setup
        # ------------------------------------------------------------------
        grid_path = os.path.join(os.path.dirname(__file__), "navmesh_grid.txt")
        try:
            with open(grid_path, "r", encoding="utf-8") as fh:
                grid = [line.rstrip("\n") for line in fh if line.strip()]
        except OSError:
            cols = int(self.view.sceneRect().width() // 40)
            rows = int(self.view.sceneRect().height() // 40)
            grid = ["." * cols for _ in range(rows)]

        self.navmesh = NavMesh.from_grid(grid)
        self._grid = grid
        self._cell_w = self.view.sceneRect().width() / len(grid[0])
        self._cell_h = self.view.sceneRect().height() / len(grid)
        # Scale portraits to a fraction of the cell size so they fit neatly on
        # the map.  Using ``min`` keeps icons square even if cells are
        # rectangular.  Icons are enlarged to roughly three times their
        # previous size to make armies more prominent on the map and then
        # reduced by 25% for a better overall fit.
        self._icon_size = int(min(self._cell_w, self._cell_h) * 0.8 * 3 * 0.6)
        self._draw_navmesh()

        # Capture mouse movement for waypoint dragging
        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)

        self.report_builder = BattlefieldReportBuilder()
        self.engine = BattlefieldEngine(report_builder=self.report_builder)

        # Mapping of army name -> icon for quick updates from engine state
        self._icons: dict[str, ArmyIcon] = {}
        # Track QGraphicsItems used to visualise movement paths for each army.
        # Each entry contains the line segments and final destination marker
        # associated with an army.  Storing them allows easy removal when the
        # path changes or the army is destroyed.
        self._paths: dict[str, list[QtWidgets.QGraphicsItem]] = {}
        self.engine.add_state_listener(self._on_engine_state)

        self.add_army_btn.clicked.connect(self._add_army)
        self.load_army_btn.clicked.connect(self._load_army)
        self.refresh_btn.clicked.connect(self._refresh_battlefield)

        self._next_x = 0
        self._dragging_icon: ArmyIcon | None = None
        self._drag_path: list[tuple[float, float]] = []
        self._snap_target: ArmyIcon | None = None
        self._drag_start: tuple[float, float] | None = None

        # Periodic engine updates (~60 FPS)
        self._last_tick = time.perf_counter()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start()

    def _on_engine_state(self, name: str, state: dict) -> None:
        """Update bars in response to engine state broadcasts."""
        icon = self._icons.get(name)
        if not icon:
            return
        ctx = self.engine._armies.get(name)
        if not ctx:
            return
        army = ctx.army
        initial = max(1.0, army.unit.initial_count)
        icon.set_health(army.current_troop_count / initial)
        rage = state.get("rage", army.current_rage)
        icon.set_rage(rage / 1000.0)

    def _on_timer_tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last_tick
        self._last_tick = now
        self.engine.tick(dt)
        for name, icon in list(self._icons.items()):
            ctx = self.engine._armies.get(name)
            if ctx is None or ctx.army.current_troop_count <= 0:
                self.scene.removeItem(icon)
                self._icons.pop(name, None)
                self._clear_path(name)
                continue
            x, y = ctx.position
            icon.setPos(x, y)
            self._update_path_visual(name, ctx.position, ctx.path)
        window = self.window()
        if window is not None and hasattr(window, "update_battlefield_reports"):
            window.update_battlefield_reports()

    # ------------------------------------------------------------------
    # Navigation mesh helpers
    # ------------------------------------------------------------------

    def _draw_navmesh(self) -> None:
        """Render the battlefield background."""

        # Draw the background image first so it sits behind all other items.
        if hasattr(self, "_background") and not self._background.isNull():
            scaled = self._background.scaled(
                int(self.view.sceneRect().width()),
                int(self.view.sceneRect().height()),
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            bg_item = self.scene.addPixmap(scaled)
            bg_item.setZValue(-2)

        # Ensure the entire battlefield fits inside the view without scrolling.
        self.view.fitInView(
            self.view.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        """Keep the entire battlefield visible when the widget is resized."""
        super().resizeEvent(event)
        self.view.fitInView(
            self.view.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

    def _cell_from_point(self, pos: tuple[float, float]) -> tuple[int, int]:
        return int(pos[0] // self._cell_w), int(pos[1] // self._cell_h)

    def _point_from_cell(self, cell: tuple[int, int]) -> tuple[float, float]:
        x, y = cell
        return (
            x * self._cell_w + self._cell_w / 2.0,
            y * self._cell_h + self._cell_h / 2.0,
        )

    def _path_between(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> list[tuple[float, float]]:
        try:
            start_cell = self._cell_from_point(start)
            end_cell = self._cell_from_point(end)
            cells = self.navmesh.astar(start_cell, end_cell)
            cells = self.navmesh.simplify_path(cells)
        except Exception:
            return []
        if not cells:
            return []
        # Convert intermediate cells back to scene coordinates but keep the
        # final waypoint exactly where the user clicked rather than snapping to
        # the centre of the grid cell.  This avoids armies drifting towards the
        # middle of a cell and allows precise positioning anywhere on the map.
        points = [self._point_from_cell(c) for c in cells[1:-1]]
        points.append(end)
        return points

    def _clear_path(self, name: str) -> None:
        """Remove any previously drawn movement path for ``name``."""
        for item in self._paths.pop(name, []):
            self.scene.removeItem(item)

    def _update_path_visual(
        self, name: str, start: tuple[float, float], path: list[tuple[float, float]]
    ) -> None:
        """Draw ``path`` for ``name`` as dotted lines ending in a marker.

        ``start`` denotes the current position of the army; ``path`` is expected
        to contain the remaining waypoints.  Existing visuals are cleared before
        drawing the new path.  If ``path`` is empty any previous visuals are
        removed and nothing is drawn."""

        self._clear_path(name)
        if not path:
            return

        pen = QtGui.QPen(
            QtCore.Qt.GlobalColor.green, 2, QtCore.Qt.PenStyle.DotLine
        )
        items: list[QtWidgets.QGraphicsItem] = []
        points = [start, *path]
        for a, b in zip(points, points[1:]):
            line = self.scene.addLine(a[0], a[1], b[0], b[1], pen)
            line.setZValue(-1)
            items.append(line)
        end = points[-1]
        radius = 4.0
        circle = self.scene.addEllipse(
            end[0] - radius,
            end[1] - radius,
            radius * 2,
            radius * 2,
            pen,
            QtGui.QBrush(QtCore.Qt.GlobalColor.transparent),
        )
        circle.setZValue(-1)
        items.append(circle)
        self._paths[name] = items

    def _add_army(self) -> None:
        dlg = ArmySetupDialog(self)
        if dlg.exec() != int(QtWidgets.QDialog.DialogCode.Accepted):
            return
        cfg = dlg.get_config()
        army = create_armies_from_data([cfg])[0]
        pos = (self._next_x, 0.0)
        self.engine.add_army(
            army,
            cfg.get("team", ""),
            position=pos,
            speed=cfg.get("speed", 50.0),
        )

        heroes = cfg.get("heroes", [])
        main_path = os.path.join(
            os.path.dirname(__file__),
            "Hero Images",
            f"{heroes[0]['hero_name_or_preset'].capitalize()}.png",
        ) if heroes else os.path.join(
            os.path.dirname(__file__), "Icons", f"{cfg['unit_type'].capitalize()}.png"
        )
        secondary_path = None
        if len(heroes) > 1:
            secondary_path = os.path.join(
                os.path.dirname(__file__),
                "Hero Images",
                f"{heroes[1]['hero_name_or_preset'].capitalize()}.png",
            )
        icon = ArmyIcon(
            main_path,
            secondary_path,
            1.0,
            army_name=army.name,
            team=cfg.get("team", ""),
            max_size=self._icon_size,
        )
        icon.set_rage(army.current_rage / 1000.0)
        icon.setPos(*pos)
        self.scene.addItem(icon)
        self._icons[army.name] = icon
        self._next_x += icon.boundingRect().width() + 10

    def _load_army(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Army", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        cfg = load_army_from_file(file_path)
        if not cfg:
            return
        army = create_armies_from_data([cfg])[0]
        pos = (self._next_x, 0.0)
        self.engine.add_army(
            army,
            cfg.get("team", ""),
            position=pos,
            speed=cfg.get("speed", 50.0),
        )

        heroes = cfg.get("heroes", [])
        main_path = os.path.join(
            os.path.dirname(__file__),
            "Hero Images",
            f"{heroes[0]['hero_name_or_preset'].capitalize()}.png",
        ) if heroes else os.path.join(
            os.path.dirname(__file__), "Icons", f"{cfg['unit_type'].capitalize()}.png"
        )
        secondary_path = None
        if len(heroes) > 1:
            secondary_path = os.path.join(
                os.path.dirname(__file__),
                "Hero Images",
                f"{heroes[1]['hero_name_or_preset'].capitalize()}.png",
            )
        icon = ArmyIcon(
            main_path,
            secondary_path,
            1.0,
            army_name=army.name,
            team=cfg.get("team", ""),
            max_size=self._icon_size,
        )
        icon.set_rage(army.current_rage / 1000.0)
        icon.setPos(*pos)
        self.scene.addItem(icon)
        # Track icons so timer updates can animate movement and health bars
        self._icons[army.name] = icon
        self._next_x += icon.boundingRect().width() + 10

    def _refresh_battlefield(self) -> None:
        """Clear all armies and reset the battlefield engine."""
        self.scene.clear()
        self._icons.clear()
        self._paths.clear()
        self._draw_navmesh()
        self._next_x = 0
        self.report_builder = BattlefieldReportBuilder()
        self.engine.reset(report_builder=self.report_builder)
        self._dragging_icon = None
        self._drag_path = []
        self._snap_target = None
        self._drag_start = None

    def add_army_icon(
        self,
        main_image: str,
        secondary_image: str | None,
        health_ratio: float,
        position: tuple[float, float],
        *,
        army_name: str | None = None,
        team: str | None = None,
    ) -> ArmyIcon:
        icon = ArmyIcon(
            main_image,
            secondary_image,
            health_ratio,
            army_name=army_name,
            team=team,
            max_size=self._icon_size,
        )
        icon.set_rage(0.0)
        icon.setPos(*position)
        self.scene.addItem(icon)
        return icon

    # ------------------------------------------------------------------
    # Mouse interaction for waypoints and engagements
    # ------------------------------------------------------------------

    def _find_enemy_near(
        self, pos: QtCore.QPointF, team: str, threshold: float = 30.0
    ) -> ArmyIcon | None:
        for item in self.scene.items():
            if (
                isinstance(item, ArmyIcon)
                and item is not self._dragging_icon
                and item.team != team
            ):
                center = item.sceneBoundingRect().center()
                if math.hypot(center.x() - pos.x(), center.y() - pos.y()) <= threshold:
                    return item
        return None

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        if obj is self.view.viewport():
            if (
                event.type() == QtCore.QEvent.Type.MouseButtonPress
                and event.button() == QtCore.Qt.MouseButton.LeftButton
            ):
                item = self.view.itemAt(event.pos())
                if isinstance(item, ArmyIcon):
                    self._dragging_icon = item
                    self._drag_path = [(item.x(), item.y())]
                    self._drag_start = (item.x(), item.y())
                    return True
            if event.type() == QtCore.QEvent.Type.MouseMove and self._dragging_icon:
                pos = self.view.mapToScene(event.pos())
                enemy = self._find_enemy_near(pos, self._dragging_icon.team or "")
                if enemy:
                    if self._snap_target and self._snap_target is not enemy:
                        self._snap_target.setOpacity(1.0)
                    self._snap_target = enemy
                    enemy.setOpacity(0.7)
                    pos = enemy.sceneBoundingRect().center()
                else:
                    if self._snap_target:
                        self._snap_target.setOpacity(1.0)
                    self._snap_target = None
                return True
            if (
                event.type() == QtCore.QEvent.Type.MouseButtonRelease
                and event.button() == QtCore.Qt.MouseButton.LeftButton
                and self._dragging_icon
            ):
                pos = self.view.mapToScene(event.pos())
                start = self._drag_start or (self._dragging_icon.x(), self._dragging_icon.y())
                if self._snap_target:
                    end_pt = self._snap_target.sceneBoundingRect().center()
                    end = (end_pt.x(), end_pt.y())
                    path = self._path_between(start, end)
                    self.engine.set_path(
                        self._dragging_icon.army_name or "",
                        path,
                    )
                    self.engine.engage(
                        self._dragging_icon.army_name or "",
                        self._snap_target.army_name or "",
                    )
                    self._update_path_visual(
                        self._dragging_icon.army_name or "", start, path
                    )
                    self._snap_target.setOpacity(1.0)
                else:
                    end = (pos.x(), pos.y())
                    path = self._path_between(start, end)
                    self.engine.set_path(
                        self._dragging_icon.army_name or "",
                        path,
                    )
                    if path:
                        self._dragging_icon.setPos(*path[-1])
                    else:
                        self._dragging_icon.setPos(pos)
                    self._update_path_visual(
                        self._dragging_icon.army_name or "", start, path
                    )
                self._dragging_icon = None
                self._drag_path = []
                self._snap_target = None
                self._drag_start = None
                return True
        return super().eventFilter(obj, event)


def _skill_stats_entry(
    army: Army,
    skill_id: str,
    name: str,
    *,
    casts_override: Any | None = None,
) -> dict[str, Any]:
    """Return aggregated statistics for ``skill_id`` from ``army``."""

    entry = {
        "id": skill_id,
        "name": name,
        "casts": army.skill_trigger_counts.get(skill_id, 0),
        "kills": int(round(army.skill_kill_totals.get(skill_id, 0.0))),
        "heals": int(round(army.skill_heal_totals.get(skill_id, 0.0))),
        "shielded": int(round(army.skill_shield_totals.get(skill_id, 0.0))),
        "rage": int(round(army.skill_rage_totals.get(skill_id, 0.0))),
        "rage_reduced": int(round(army.skill_rage_reduction_totals.get(skill_id, 0.0))),
        "damage_reduced": int(round(army.skill_damage_reduction_totals.get(skill_id, 0.0))),
        "boosted_kills": int(round(army.skill_kill_boost_totals.get(skill_id, 0.0))),
        "boosted_heals": int(round(army.skill_heal_boost_totals.get(skill_id, 0.0))),
        "boosted_shielded": int(round(army.skill_shield_boost_totals.get(skill_id, 0.0))),
        "boosted_rage": int(round(army.skill_rage_boost_totals.get(skill_id, 0.0))),
        "boosted_rage_reduced": int(
            round(army.skill_rage_reduction_boost_totals.get(skill_id, 0.0))
        ),
        "boosted_damage_reduced": int(
            round(army.skill_damage_reduction_boost_totals.get(skill_id, 0.0))
        ),
    }
    if casts_override is not None:
        entry["casts"] = casts_override
    return entry


def _is_mount_skill(skill_id: str) -> bool:
    skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id) or {}
    skill_type = skill_def.get("type")
    if isinstance(skill_type, SkillType) and skill_type.name.endswith("MOUNT_SKILL"):
        return True
    if isinstance(skill_type, str) and skill_type.upper().endswith("MOUNT_SKILL"):
        return True
    if skill_def.get("is_mount_skill") or skill_def.get("mount_skill"):
        return True
    source_val = skill_def.get("source") or skill_def.get("origin")
    return isinstance(source_val, str) and source_val.lower() == "mount"


def _resolve_portraits(cfg: dict) -> tuple[str, str]:
    """Return portrait paths for the heroes defined in ``cfg``."""

    heroes_cfg = cfg.get("heroes", []) or []
    base_dir = os.path.dirname(__file__)
    if heroes_cfg:
        first_name = heroes_cfg[0].get("hero_name_or_preset", "")
        portrait1 = os.path.join(
            base_dir,
            "Hero Images",
            f"{first_name.capitalize()}.png",
        )
        if len(heroes_cfg) > 1:
            second_name = heroes_cfg[1].get("hero_name_or_preset", "")
            portrait2 = os.path.join(
                base_dir,
                "Hero Images",
                f"{second_name.capitalize()}.png",
            )
        else:
            portrait2 = ""
    else:
        unit_type = cfg.get("unit_type", "")
        portrait1 = os.path.join(
            base_dir,
            "Icons",
            f"{unit_type.capitalize()}.png",
        )
        portrait2 = ""
    return portrait1, portrait2


def build_army_skill_summary(army: Army, cfg: dict, team: str) -> dict[str, Any]:
    """Collect hero skill statistics for ``army`` using ``cfg`` metadata."""

    portrait1, portrait2 = _resolve_portraits(cfg)
    heroes_cfg = cfg.get("heroes", []) or []
    hero_names = [h.get("hero_name_or_preset", "").capitalize() for h in heroes_cfg]

    skill_lists: list[list[dict[str, Any]]] = []
    hero_mount_skill_ids: list[set[str]] = []
    for hero_idx, hero in enumerate(army.heroes):
        hero_entries: list[dict[str, Any]] = []
        hero_entries.append(
            _skill_stats_entry(army, "base_rage", "Base Rage", casts_override="")
        )
        for sid, sname in (("basic_attack", "Basic Attack"), ("counter_attack", "Counterattack")):
            hero_entries.append(_skill_stats_entry(army, sid, sname))
        for skill_def in getattr(hero, "skills", []) or []:
            if skill_def.get("id") == "dummy_talent_empty":
                continue
            sid = skill_def.get("id", "")
            hero_entries.append(
                _skill_stats_entry(army, sid, skill_def.get("name", sid))
            )
        cfg_mount_ids: set[str] = set()
        hero_cfg = heroes_cfg[hero_idx] if hero_idx < len(heroes_cfg) else {}
        if isinstance(hero_cfg, dict):
            mount_ids_cfg = hero_cfg.get("mount_skill_ids", []) or []
            if isinstance(mount_ids_cfg, (list, tuple, set)):
                cfg_mount_ids.update(str(sid) for sid in mount_ids_cfg if isinstance(sid, str))
        for sid in getattr(hero, "mount_skill_ids", []) or []:
            if isinstance(sid, str) and sid:
                cfg_mount_ids.add(str(sid))
        for entry in hero_entries:
            if isinstance(entry, dict) and str(entry.get("id", "")) in cfg_mount_ids:
                entry["is_mount"] = True
        hero_mount_skill_ids.append(cfg_mount_ids)
        skill_lists.append(hero_entries)

    gem_skill_ids = getattr(army, "gem_skill_ids", {}) or {}
    if gem_skill_ids:
        if not skill_lists:
            skill_lists.append([])

        gem_entries_by_idx: dict[int, list[tuple[tuple[int, int, str], dict[str, Any]]]] = {}
        for slot, skill_id in gem_skill_ids.items():
            if not isinstance(skill_id, str) or not skill_id:
                continue
            skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id)
            if not skill_def:
                continue
            hero_index = JEWEL_SLOT_HERO_INDEX.get(slot, 0)
            target_index = hero_index if hero_index >= 0 else 0
            while len(skill_lists) <= target_index:
                skill_lists.append([])
            entry = _skill_stats_entry(
                army,
                skill_id,
                skill_def.get("name", skill_id),
            )
            config = skill_def.get("config", {}) or {}
            entry["rarity"] = config.get("rarity")
            rarity_sort = _RARITY_SORT_ORDER.get(entry.get("rarity"), 99)
            ui_order = int(config.get("ui_order", 0))
            sort_key = (rarity_sort, ui_order, entry.get("name", skill_id))
            bucket = gem_entries_by_idx.setdefault(target_index, [])
            bucket.append((sort_key, entry))

        for idx, entries in gem_entries_by_idx.items():
            entries.sort(key=lambda item: item[0])
            skill_lists[idx].extend(entry for _, entry in entries)

    mount_skill_ids: set[str] = set()
    stats_maps: list[dict[str, float]] = [
        army.skill_trigger_counts,
        army.skill_kill_totals,
        army.skill_heal_totals,
        army.skill_shield_totals,
        army.skill_rage_totals,
        army.skill_rage_reduction_totals,
        army.skill_damage_reduction_totals,
        army.skill_kill_boost_totals,
        army.skill_heal_boost_totals,
        army.skill_shield_boost_totals,
        army.skill_rage_boost_totals,
        army.skill_rage_reduction_boost_totals,
        army.skill_damage_reduction_boost_totals,
    ]
    for stat_map in stats_maps:
        for skill_id, value in stat_map.items():
            if not skill_id or skill_id in mount_skill_ids:
                continue
            if not _is_mount_skill(skill_id):
                continue
            if abs(float(value)) <= 1e-9:
                continue
            mount_skill_ids.add(skill_id)

    def _add_mount_entry(hero_index: int, skill_id: str) -> None:
        if not isinstance(skill_id, str) or not skill_id:
            return
        while len(skill_lists) <= hero_index:
            skill_lists.append([])
        target_list = skill_lists[hero_index]
        skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id) or {}
        for entry in target_list:
            if isinstance(entry, dict) and entry.get("id") == skill_id:
                entry["is_mount"] = True
                entry.setdefault("source", skill_def.get("source") or skill_def.get("origin") or "mount")
                entry.setdefault("type", skill_def.get("type"))
                return
        entry = _skill_stats_entry(
            army,
            skill_id,
            skill_def.get("name", skill_id),
        )
        entry["is_mount"] = True
        entry["source"] = skill_def.get("source") or skill_def.get("origin") or "mount"
        entry["type"] = skill_def.get("type")
        target_list.append(entry)

    for idx, mount_ids in enumerate(hero_mount_skill_ids):
        for skill_id in sorted(mount_ids):
            _add_mount_entry(idx, skill_id)

    if mount_skill_ids:
        for skill_id in sorted(mount_skill_ids):
            target_indices = [
                idx for idx, mount_ids in enumerate(hero_mount_skill_ids) if skill_id in mount_ids
            ]
            if not target_indices:
                target_indices = [0]
            for hero_index in target_indices:
                _add_mount_entry(hero_index, skill_id)

    passive_bonus_entries = iter_skill_bonus_entries_from_effects(
        getattr(army, "active_effects", [])
    )

    return {
        "team": team,
        "name": army.name,
        "portrait1": portrait1,
        "portrait2": portrait2,
        "remaining": int(round(army.current_troop_count)),
        "initial": int(round(army.unit.initial_count)),
        "healed": int(round(army.troops_healed_total)),
        "kills": int(round(sum(army.kills_dealt_history))),
        "skills": skill_lists,
        "hero_names": hero_names,
        "passive_bonus_entries": passive_bonus_entries,
    }


def build_skill_summaries(armies: list[Army], configs: list[dict]) -> list[dict[str, Any]]:
    """Return summary dictionaries for each ``army`` in order."""

    summaries: list[dict[str, Any]] = []
    for idx, army in enumerate(armies):
        cfg = configs[idx] if idx < len(configs) else {}
        team = "red" if idx == 0 else "blue"
        summaries.append(build_army_skill_summary(army, cfg, team))
    return summaries


class SimulationWorker(QtCore.QThread):
    progress_update = QtCore.pyqtSignal(int, int)
    finished_text = QtCore.pyqtSignal(str, object, object)
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        setup_data: list[dict],
        runs: int,
        num_workers: int,
        seed_target: SeedTarget | None = None,
        dynamic_settings: dict[str, float] | None = None,
        *,
        hero_cooldowns_enabled: bool = True,
        plugin_cooldowns_enabled: bool = True,
        gem_cooldowns_enabled: bool = True,
        mount_cooldowns_enabled: bool = True,
    ) -> None:
        super().__init__()
        self.setup_data = setup_data
        self.runs = runs
        self.num_workers = num_workers
        self.seed_target = dict(seed_target) if seed_target else None
        self._cancelled = threading.Event()
        self.dynamic_settings = dict(dynamic_settings) if dynamic_settings else None
        self.win_rate: float | None = None
        self.best_match: dict[str, Any] | None = None
        self.sample_battle_stats: dict[str, Any] | None = None
        self.hero_cooldowns_enabled: bool = bool(hero_cooldowns_enabled)
        self.plugin_cooldowns_enabled: bool = bool(plugin_cooldowns_enabled)
        self.gem_cooldowns_enabled: bool = bool(gem_cooldowns_enabled)
        self.mount_cooldowns_enabled: bool = bool(mount_cooldowns_enabled)

    def cancel(self) -> None:
        """Request the simulation to stop."""
        self._cancelled.set()

    def run(self) -> None:
        try:
            def progress_cb(done: int, total: int) -> None:
                self.progress_update.emit(done, total)
                if self._cancelled.is_set():
                    raise RuntimeError("cancelled")

            if self.dynamic_settings is not None:
                dynamic_unrevivable_config.apply_session_settings(self.dynamic_settings)

            win_rate, best_match = run_additional_simulations(
                self.setup_data,
                runs=self.runs,
                verbose=False,
                progress_callback=progress_cb,
                num_workers=self.num_workers,
                target_outcome=self.seed_target,
                cooldowns_enabled=self.hero_cooldowns_enabled,
                hero_cooldowns_enabled=self.hero_cooldowns_enabled,
                plugin_cooldowns_enabled=self.plugin_cooldowns_enabled,
                gem_cooldowns_enabled=self.gem_cooldowns_enabled,
                mount_cooldowns_enabled=self.mount_cooldowns_enabled,
            )
            self.win_rate = float(win_rate)
            self.best_match = dict(best_match) if isinstance(best_match, dict) else None
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            seed = best_match.get("seed") if best_match else None
            if seed is not None:
                random.seed(int(seed))

            active_settings = None
            if best_match:
                match_settings = best_match.get("dynamic_settings")
                if isinstance(match_settings, dict):
                    active_settings = dict(match_settings)
            if active_settings is None:
                active_settings = self.dynamic_settings
            if active_settings is not None:
                dynamic_unrevivable_config.apply_session_settings(active_settings)
                self.dynamic_settings = dict(active_settings)

            multiplier = None
            if best_match:
                multiplier = best_match.get("troop_scalar_multiplier")
            if multiplier is None:
                multiplier = troop_scalar_config.get_multiplier()
            troop_scalar_config.set_session_multiplier(float(multiplier))

            armies = create_armies_from_data(self.setup_data)
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            report_builder = ReportBuilder(use_color=False)
            sim = GameSimulator(
                armies[0],
                armies[1],
                report_builder,
                track_stats=True,
                cooldowns_enabled=self.hero_cooldowns_enabled,
                hero_cooldowns_enabled=self.hero_cooldowns_enabled,
                plugin_cooldowns_enabled=self.plugin_cooldowns_enabled,
                gem_cooldowns_enabled=self.gem_cooldowns_enabled,
                mount_cooldowns_enabled=self.mount_cooldowns_enabled,
            )
            report_text = sim.simulate_battle()
            rounds = report_builder.get_rounds()
            summary = build_skill_summaries(armies, self.setup_data)
            self.sample_battle_stats = {
                "round_count": int(sim.round),
                "army_histories": [
                    {
                        "name": army.name,
                        "troops": [int(round(float(val))) for val in army.troop_count_history],
                        "unrevivable": [
                            int(round(float(val))) for val in army.unrevivable_history
                        ],
                    }
                    for army in armies
                ],
            }
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            result_text = (
                report_text
                + f"\nWin rate for {armies[0].name}: {win_rate*100:.1f}% over {self.runs} runs.\n"
            )
            self.finished_text.emit(result_text, rounds, summary)
        except RuntimeError as exc:  # pragma: no cover - GUI feedback
            if str(exc) == "cancelled":
                self.finished_text.emit("Simulation cancelled.", [], [])
            else:
                self.error.emit(str(exc))
        except Exception as exc:  # pragma: no cover - GUI feedback
            self.error.emit(str(exc))


class ArenaBatchWorker(QtCore.QThread):
    progress_update = QtCore.pyqtSignal(int, int)
    finished_dict = QtCore.pyqtSignal(dict)

    def __init__(
        self,
        layout_entries: list[dict[str, Any]],
        runs: int,
        num_workers: int,
        targeting_mode: str,
    ) -> None:
        super().__init__()
        self.layout_entries = layout_entries
        self.runs = runs
        self.num_workers = num_workers
        self._cancelled = threading.Event()
        self.targeting_mode = targeting_mode or "legacy"

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        results: dict[str, int] = {}

        def _simulate(_: int) -> str:
            armies = create_armies_from_data([dict(e["cfg"]) for e in self.layout_entries])
            battle_layout: dict[str, list[dict[str, Any]]] = {}
            for army, entry in zip(armies, self.layout_entries):
                battle_layout.setdefault(entry["team"], []).append(
                    {
                        "army": army,
                        "position": entry["position"],
                        "column": entry["column"],
                        "row": entry["row"],
                        "speed": entry["speed"],
                    }
                )
            engine = ArenaEngine()
            engine.start_arena_battle(battle_layout, targeting_mode=self.targeting_mode)
            while True:
                engine.tick(0.016)
                alive = {
                    ctx.team
                    for ctx in engine._armies.values()
                    if ctx.army.current_troop_count > 0
                }
                if len(alive) <= 1:
                    break
            return next(iter(alive)) if alive else "None"

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as pool:
            futures = [pool.submit(_simulate, i) for i in range(self.runs)]
            for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                if self._cancelled.is_set():
                    break
                winner = fut.result()
                results[winner] = results.get(winner, 0) + 1
                self.progress_update.emit(i, self.runs)

        self.finished_dict.emit(results)


class ArenaTab(QtWidgets.QWidget):
    """Simplified tab for arena maps with army controls.

    The layout mirrors :class:`BattlefieldTab` by providing a basic control
    bar and a graphics view for rendering an arena.  Actual arena mechanics
    are implemented elsewhere; this widget primarily establishes the
    structure so a dedicated tab can be added to the interface.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        controls = QtWidgets.QHBoxLayout()
        self.save_layout_btn = QtWidgets.QPushButton("Save Layout")
        self.load_layout_btn = QtWidgets.QPushButton("Load Layout")
        self.position_layout_btn = QtWidgets.QPushButton("Position Layout")
        self.position_layout_btn.setCheckable(True)
        self.load_pos_layout_btn = QtWidgets.QPushButton("Load Position Layout")
        self.refresh_btn = QtWidgets.QPushButton("Refresh Arena")
        self.swap_btn = QtWidgets.QPushButton("Swap Teams")
        self.targeting_combo = QtWidgets.QComboBox()
        self.targeting_combo.addItem("Legacy", "legacy")
        self.targeting_combo.addItem("STR", "str")
        self.targeting_combo.addItem("FRG", "frg")
        self.run_batch_btn = QtWidgets.QPushButton("Run Batch")
        self.run_btn = QtWidgets.QPushButton("Run Arena")
        self.last_run_btn = QtWidgets.QPushButton("Run Last")
        self.speed_btn = QtWidgets.QPushButton("Speed 1x")
        self.time_label = QtWidgets.QLabel("00:00")
        for btn in (
            self.save_layout_btn,
            self.load_layout_btn,
            self.position_layout_btn,
            self.load_pos_layout_btn,
            self.refresh_btn,
            self.swap_btn,
            self.targeting_combo,
            self.run_batch_btn,
            self.run_btn,
            self.last_run_btn,
            self.speed_btn,
        ):
            controls.addWidget(btn)
        controls.addWidget(self.time_label)
        controls.addStretch()
        layout.addLayout(controls)

        self._setups_dir = os.path.join(os.path.dirname(__file__), "setups")
        self.saved_armies_file = os.path.join(self._setups_dir, "saved_armies.json")
        self.last_layout_file = os.path.join(self._setups_dir, "_last_arena_layout.json")
        self.formation_file = os.path.join(self._setups_dir, "formations.json")
        self._editing_positions = False

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.view.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Load the same battlefield background so the arena map aligns with
        # the navigation mesh.  Fall back to a default size if the image is
        # missing which may be the case in tests.
        bg_path = os.path.join(
            os.path.dirname(__file__), "Icons", "BattlefieldBackground.png"
        )
        self._background = QtGui.QPixmap(bg_path)
        if not self._background.isNull():
            self.view.setSceneRect(
                0, 0, self._background.width(), self._background.height()
            )
        else:  # pragma: no cover - image may be absent in CI
            self.view.setSceneRect(0, 0, 800, 600)
        layout.addWidget(self.view, 1)

        # --------------------------------------------------------------
        # Navigation mesh setup
        # --------------------------------------------------------------
        grid_path = os.path.join(os.path.dirname(__file__), "navmesh_grid.txt")
        try:
            with open(grid_path, "r", encoding="utf-8") as fh:
                grid = [line.rstrip("\n") for line in fh if line.strip()]
        except OSError:
            cols = int(self.view.sceneRect().width() // 40)
            rows = int(self.view.sceneRect().height() // 40)
            grid = ["." * cols for _ in range(rows)]

        self.navmesh = NavMesh.from_grid(grid)
        self._grid = grid
        self._cell_w = self.view.sceneRect().width() / len(grid[0])
        self._cell_h = self.view.sceneRect().height() / len(grid)
        self._icon_size = int(min(self._cell_w, self._cell_h) * 0.8 * 3 * 0.6)
        self._draw_navmesh()

        # Pre-compute default arena slot coordinates for both teams.  The
        # layout is symmetrical around the scene centre.  ``D`` represents the
        # base separation which is derived from the default army speed
        # (``50`` units/s).  Front rows are positioned ``±D/2`` from the
        # centre while back rows are a further ``D`` behind the fronts.  Four
        # columns are spaced ``D`` apart laterally.
        self.slot_coords = self._compute_slot_coords()

        # Prepare engine and tracking structures for armies placed in slots.
        self.report_builder = BattlefieldReportBuilder()
        self.engine = ArenaEngine(report_builder=self.report_builder)
        self.engine.add_state_listener(self._on_engine_state)
        self._icons: dict[str, ArmyIcon] = {}
        self._slot_items: dict[tuple[str, int], SlotItem] = {}
        self._slot_army: dict[tuple[str, int], dict[str, Any] | None] = {}

        self._running = False
        self._last_tick = time.perf_counter()
        self._speed_multiplier = 1.0
        self._battle_time = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_timer_tick)

        radius = min(self._cell_w, self._cell_h) * 0.15
        for team, coords in self.slot_coords.items():
            for idx, (x, y) in enumerate(coords):
                item = SlotItem(team, idx, radius, self._slot_clicked, self._cell_w, self._cell_h)
                item.setFlag(
                    QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                    self._editing_positions,
                )
                item.setPos(x, y)
                self.scene.addItem(item)
                self._slot_items[(team, idx)] = item
                self._slot_army[(team, idx)] = None

        # Attempt to load a persisted position layout called "MainLayout" so
        # the arena opens with a user customised formation if available.
        # Failing to load simply leaves the computed coordinates in place.
        try:
            self._load_formation_layout("MainLayout")
        except Exception:
            # Silently ignore any issues (missing file, JSON errors, etc.).
            pass

        self.position_layout_btn.toggled.connect(self._toggle_position_layout)
        self.load_pos_layout_btn.clicked.connect(self._prompt_load_formation)
        self.refresh_btn.clicked.connect(self._refresh_arena)
        self.save_layout_btn.clicked.connect(self._save_layout)
        self.load_layout_btn.clicked.connect(self._load_layout)
        self.swap_btn.clicked.connect(self._swap_teams)
        self.run_batch_btn.clicked.connect(self._run_batch)
        self.run_btn.clicked.connect(self._run_arena)
        self.last_run_btn.clicked.connect(self._run_last_layout)
        self.speed_btn.clicked.connect(self._toggle_speed)

    # ------------------------------------------------------------------
    def _compute_slot_coords(self) -> dict[str, list[tuple[float, float]]]:
        """Return coordinates for each deployment slot of both teams."""

        default_speed = 50.0
        engage_dist = 4 * default_speed + ENGAGEMENT_DISTANCE  # meet opposing front in 2 s
        to_mid = engage_dist / 2.0  # distance from front line to map centre
        back_offset = default_speed * 2  # back row reaches enemy front in 4 s

        cx = self.view.sceneRect().width() / 2.0
        cy = self.view.sceneRect().height() / 2.0

        # Vertical offsets for the four columns relative to the centre.  Rows are
        # spaced 50% further apart but diagonal attackers receive a temporary
        # speed boost so engagements still occur after exactly 2 s.
        row_step = default_speed * 1.5
        offsets = [
            -1.5 * row_step,
            -0.5 * row_step,
            0.5 * row_step,
            1.5 * row_step,
        ]

        team1 = [(cx - to_mid, cy + dy) for dy in offsets]
        team1 += [(cx - to_mid - back_offset, cy + dy) for dy in offsets]

        team2 = [(cx + to_mid, cy + dy) for dy in offsets]
        team2 += [(cx + to_mid + back_offset, cy + dy) for dy in offsets]

        return {"team1": team1, "team2": team2}

    def _slot_clicked(self, team: str, index: int) -> None:
        """Handle clicks on deployment slots to add armies."""

        if self._running:
            return
        key = (team, index)

        existing = self._slot_army.get(key)

        dlg = ArmySetupDialog(self)
        default_team = "red" if team == "team1" else "blue"
        if existing:
            # Pre-populate the dialog with the existing army configuration so
            # users can edit armies already placed on the battlefield.
            cfg = existing.get("config", {})
            dlg.frame.populate_from_config(cfg)
            dlg.team_combo.setCurrentText(existing.get("team", default_team))
            dlg.speed_spin.setValue(existing.get("speed", 50.0))
        else:
            dlg.team_combo.setCurrentText(default_team)

        if dlg.exec() != int(QtWidgets.QDialog.DialogCode.Accepted):
            return
        cfg = dlg.get_config()
        cfg["team"] = default_team
        army = create_armies_from_data([cfg])[0]
        pos = self.slot_coords[team][index]

        # Remove any existing icon if the slot is being edited.
        if existing:
            old_icon = self._icons.pop(existing["army"].name, None)
            if old_icon is not None:
                self.scene.removeItem(old_icon)

        heroes = cfg.get("heroes", [])
        main_path = (
            os.path.join(
                os.path.dirname(__file__),
                "Hero Images",
                f"{heroes[0]['hero_name_or_preset'].capitalize()}.png",
            )
            if heroes
            else os.path.join(
                os.path.dirname(__file__),
                "Icons",
                f"{cfg['unit_type'].capitalize()}.png",
            )
        )
        secondary_path = None
        if len(heroes) > 1:
            secondary_path = os.path.join(
                os.path.dirname(__file__),
                "Hero Images",
                f"{heroes[1]['hero_name_or_preset'].capitalize()}.png",
            )
        icon = ArmyIcon(
            main_path,
            secondary_path,
            1.0,
            army_name=army.name,
            team=cfg["team"],
            max_size=self._icon_size,
            on_drop=self._on_icon_drop,
            on_double_click=self._icon_double_clicked,
        )
        icon.set_rage(army.current_rage / 1000.0)
        icon.setPos(*pos)
        self.scene.addItem(icon)
        self._icons[army.name] = icon
        # Store the full configuration for later persistence so layouts can be
        # reloaded without requiring a separate ``saved_armies`` file.  This
        # also retains the custom movement speed configured for the army.
        self._slot_army[key] = {
            "army": army,
            "team": cfg["team"],
            "speed": cfg.get("speed", 50.0),
            "config": cfg,
        }

    def _assign_team(self, info: dict[str, Any], team: str) -> None:
        """Update team information in the army info structure."""

        new_team = "red" if team == "team1" else "blue"
        info["team"] = new_team
        cfg = info.get("config")
        if cfg is not None:
            cfg["team"] = new_team

    def _icon_double_clicked(self, army_name: str) -> None:
        """Open the setup dialog for the army's slot when its icon is double-clicked."""

        if self._running:
            return
        for (team, idx), info in self._slot_army.items():
            if info and info["army"].name == army_name:
                self._slot_clicked(team, idx)
                break

    def _on_icon_drop(self, army_name: str, pos: QtCore.QPointF) -> None:
        """Handle an army icon being dropped somewhere in the scene."""

        if self._running:
            return
        target: tuple[str, int] | None = None
        for (team, idx), item in self._slot_items.items():
            if item.contains(item.mapFromScene(pos)):
                target = (team, idx)
                break
        if target is None:
            # Snap back to original slot
            key = next(
                (k for k, info in self._slot_army.items() if info and info["army"].name == army_name),
                None,
            )
            if key:
                icon = self._icons[army_name]
                icon.setPos(*self.slot_coords[key[0]][key[1]])
            return
        self._relocate_army(army_name, target)

    def _relocate_army(self, army_name: str, target: tuple[str, int]) -> None:
        """Move an army to a new slot, swapping if necessary."""

        current_key = next(
            (k for k, info in self._slot_army.items() if info and info["army"].name == army_name),
            None,
        )
        if current_key is None:
            return
        if current_key == target:
            icon = self._icons[army_name]
            icon.setPos(*self.slot_coords[target[0]][target[1]])
            return

        moving = self._slot_army[current_key]
        other = self._slot_army.get(target)

        self._slot_army[target] = moving
        self._assign_team(moving, target[0])
        icon = self._icons[army_name]
        icon.setPos(*self.slot_coords[target[0]][target[1]])
        icon.team = moving["team"]

        if other:
            self._slot_army[current_key] = other
            self._assign_team(other, current_key[0])
            other_icon = self._icons[other["army"].name]
            other_icon.setPos(*self.slot_coords[current_key[0]][current_key[1]])
            other_icon.team = other["team"]
        else:
            self._slot_army[current_key] = None

    def _swap_teams(self) -> None:
        """Swap armies between teams while mirroring their positions."""

        if self._running:
            return
        total = len(self.slot_coords["team1"])
        for idx in range(total):
            key1 = ("team1", idx)
            key2 = ("team2", idx)
            info1 = self._slot_army.get(key1)
            info2 = self._slot_army.get(key2)
            self._slot_army[key1], self._slot_army[key2] = info2, info1
            if info1:
                icon1 = self._icons.get(info1["army"].name)
                if icon1:
                    icon1.setPos(*self.slot_coords["team2"][idx])
                    self._assign_team(info1, "team2")
                    icon1.team = info1["team"]
            if info2:
                icon2 = self._icons.get(info2["army"].name)
                if icon2:
                    icon2.setPos(*self.slot_coords["team1"][idx])
                    self._assign_team(info2, "team1")
                    icon2.team = info2["team"]

    def _collect_layout_data(self) -> dict[str, Any]:
        """Return layout entries and metadata for all occupied slots."""

        entries: list[dict[str, Any]] = []
        for (team, idx), info in self._slot_army.items():
            if not info:
                continue
            col = idx % 4
            row = idx // 4
            entry: dict[str, Any] = {
                "army_name": info["army"].name,
                "team": team,
                "column": col,
                "row": row,
                "speed": info.get("speed", 50.0),
            }
            cfg = info.get("config")
            if cfg:
                entry["config"] = cfg
            entries.append(entry)
        return {
            "targeting_mode": self.targeting_combo.currentData(),
            "entries": entries,
        }

    def _save_last_layout(self) -> None:
        """Persist the current layout for quick access later."""

        data = self._collect_layout_data()
        entries = data.get("entries", []) if isinstance(data, dict) else data
        if not entries:
            return
        os.makedirs(self._setups_dir, exist_ok=True)
        try:
            with open(self.last_layout_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError:
            pass

    def _save_layout(self) -> None:
        """Persist current slot assignments to a JSON file."""

        data = self._collect_layout_data()
        entries = data.get("entries", []) if isinstance(data, dict) else data
        if not entries:
            QtWidgets.QMessageBox.information(
                self, "Nothing to save", "No armies are placed in the arena."
            )
            return

        os.makedirs(self._setups_dir, exist_ok=True)
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Arena Layout", self._setups_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:  # pragma: no cover - GUI feedback
            QtWidgets.QMessageBox.warning(self, "Save failed", str(exc))

    def _load_layout(self) -> None:
        """Load slot assignments from disk and rebuild armies."""

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Arena Layout", self._setups_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                layout_data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - GUI feedback
            QtWidgets.QMessageBox.warning(self, "Load failed", str(exc))
            return
        self._apply_layout(layout_data)

    def _apply_layout(self, layout_data: Any) -> None:
        """Apply a previously saved layout to the arena."""

        try:
            with open(self.saved_armies_file, "r", encoding="utf-8") as fh:
                saved_armies = json.load(fh)
        except (OSError, json.JSONDecodeError):
            # Missing or invalid ``saved_armies`` should not block loading –
            # layouts now embed full army configs so we can continue without it.
            saved_armies = {}

        self._refresh_arena()
        entries = layout_data
        targeting_mode = None
        if isinstance(layout_data, dict):
            entries = layout_data.get("entries", [])
            targeting_mode = layout_data.get("targeting_mode")
        if targeting_mode:
            idx = self.targeting_combo.findData(targeting_mode)
            if idx != -1:
                self.targeting_combo.setCurrentIndex(idx)
        for entry in entries:
            name = entry.get("army_name")
            team = entry.get("team")
            col = entry.get("column")
            row = entry.get("row")
            if (
                not isinstance(name, str)
                or team not in self.slot_coords
                or not isinstance(col, int)
                or not isinstance(row, int)
            ):
                continue
            cfg = entry.get("config") or saved_armies.get(name)
            if not cfg:
                continue
            cfg = dict(cfg)
            cfg["team"] = "red" if team == "team1" else "blue"
            cfg["speed"] = entry.get("speed", cfg.get("speed", 50.0))
            army = create_armies_from_data([cfg])[0]
            index = row * 4 + col
            pos = self.slot_coords[team][index]

            heroes = cfg.get("heroes", [])
            main_path = (
                os.path.join(
                    os.path.dirname(__file__),
                    "Hero Images",
                    f"{heroes[0]['hero_name_or_preset'].capitalize()}.png",
                )
                if heroes
                else os.path.join(
                    os.path.dirname(__file__), "Icons", f"{cfg['unit_type'].capitalize()}.png"
                )
            )
            secondary_path = None
            if len(heroes) > 1:
                secondary_path = os.path.join(
                    os.path.dirname(__file__),
                    "Hero Images",
                    f"{heroes[1]['hero_name_or_preset'].capitalize()}.png",
                )
            icon = ArmyIcon(
                main_path,
                secondary_path,
                1.0,
                army_name=army.name,
                team=cfg["team"],
                max_size=self._icon_size,
                on_drop=self._on_icon_drop,
                on_double_click=self._icon_double_clicked,
            )
            icon.set_rage(army.current_rage / 1000.0)
            icon.setPos(*pos)
            self.scene.addItem(icon)
            self._icons[army.name] = icon
            info = {
                "army": army,
                "team": cfg["team"],
                "speed": cfg.get("speed", 50.0),
                "config": cfg,
            }
            self._assign_team(info, team)
            icon.team = info["team"]
            self._slot_army[(team, index)] = info

    def _toggle_position_layout(self, checked: bool) -> None:
        """Enable or disable slot position editing."""
        self._editing_positions = checked
        flag = QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        for item in self._slot_items.values():
            item.setFlag(flag, checked)
            if not checked:
                item.snap_to_grid()
        if not checked:
            # Update stored coordinates and prompt to save
            self._update_slot_coords_from_items()
            name, ok = QtWidgets.QInputDialog.getText(
                self, "Save Formation", "Formation name:", text="default"
            )
            if ok and name:
                self._save_formation_layout(name)

    def _update_slot_coords_from_items(self) -> None:
        """Refresh ``slot_coords`` from the current slot item positions."""
        for (team, idx), item in self._slot_items.items():
            pos = item.pos()
            coord = (pos.x(), pos.y())
            self.slot_coords[team][idx] = coord
            info = self._slot_army.get((team, idx))
            if info:
                icon = self._icons.get(info["army"].name)
                if icon:
                    icon.setPos(*coord)

    def _save_formation_layout(self, name: str) -> None:
        """Persist current slot coordinates under ``name``."""
        data = {"team1": self.slot_coords["team1"], "team2": self.slot_coords["team2"]}
        os.makedirs(self._setups_dir, exist_ok=True)
        try:
            existing: dict[str, Any]
            with open(self.formation_file, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except (OSError, json.JSONDecodeError):
            existing = {}
        existing[name] = data
        try:
            with open(self.formation_file, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2)
        except OSError:
            pass

    def _prompt_load_formation(self) -> None:
        """Prompt the user to load a previously saved formation layout."""
        try:
            with open(self.formation_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not data:
            QtWidgets.QMessageBox.information(
                self, "No Formations", "No saved position layouts found."
            )
            return
        names = sorted(data.keys())
        name, ok = QtWidgets.QInputDialog.getItem(
            self, "Load Formation", "Formation:", names, 0, False
        )
        if ok and name:
            self._load_formation_layout(name)

    def _load_formation_layout(self, name: str) -> None:
        """Load slot coordinates from a saved formation."""
        try:
            with open(self.formation_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        formation = data.get(name)
        if not formation:
            return
        for team, coords in formation.items():
            for idx, (x, y) in enumerate(coords):
                self.slot_coords[team][idx] = (x, y)
                item = self._slot_items.get((team, idx))
                if item:
                    item.setPos(x, y)
                info = self._slot_army.get((team, idx))
                if info:
                    icon = self._icons.get(info["army"].name)
                    if icon:
                        icon.setPos(x, y)

    def _run_last_layout(self) -> None:
        """Load the last saved layout and immediately run it."""

        try:
            with open(self.last_layout_file, "r", encoding="utf-8") as fh:
                layout_data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            QtWidgets.QMessageBox.information(
                self, "No Layout", "No previous arena layout found."
            )
            return
        self._apply_layout(layout_data)
        self._run_arena()

    def _run_arena(self) -> None:
        """Start the arena battle and disable slot manipulation."""

        if self._running:
            return
        layout: dict[str, list[dict[str, Any]]] = {}
        for (slot_team, idx), info in self._slot_army.items():
            if not info:
                continue
            col = idx % 4
            row = idx // 4
            pos = self.slot_coords[slot_team][idx]
            layout.setdefault(info["team"], []).append(
                {
                    "army": info["army"],
                    "position": pos,
                    "column": col,
                    "row": row,
                    "speed": info.get("speed", 50.0),
                }
            )
        if not layout:
            return
        self._save_last_layout()
        self.engine.reset(report_builder=self.report_builder)
        targeting_mode = self.targeting_combo.currentData()
        self.engine.start_arena_battle(layout, targeting_mode=targeting_mode)
        self._running = True
        self.run_btn.setEnabled(False)
        for item in self._slot_items.values():
            item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self._last_tick = time.perf_counter()
        self._battle_time = 0.0
        self._update_time_label()
        self._timer.start()

    def _run_batch(self, checked: bool = False, *, count: int | None = None) -> None:
        """Run multiple arena battles and record victory distribution.

        Parameters
        ----------
        checked:
            Unused. Accepts the ``clicked`` signal's boolean argument so the
            method can be connected directly to :py:meth:`QPushButton.clicked`.
        count:
            When provided the batch runs synchronously for tests.  When ``None``
            (the default for GUI usage) the batch is executed in a worker thread
            and progress is reported via the main window's progress bar.
        """

        layout_entries: list[dict[str, Any]] = []
        for (slot_team, idx), info in self._slot_army.items():
            if not info or not info.get("config"):
                continue
            col = idx % 4
            row = idx // 4
            pos = self.slot_coords[slot_team][idx]
            layout_entries.append(
                {
                    "cfg": info["config"],
                    "team": info["team"],
                    "position": pos,
                    "column": col,
                    "row": row,
                    "speed": info.get("speed", 50.0),
                }
            )
        if not layout_entries:
            return

        targeting_mode = self.targeting_combo.currentData()
        if count is not None:
            results: dict[str, int] = {}
            for _ in range(count):
                armies = create_armies_from_data([dict(e["cfg"]) for e in layout_entries])
                battle_layout: dict[str, list[dict[str, Any]]] = {}
                for army, entry in zip(armies, layout_entries):
                    battle_layout.setdefault(entry["team"], []).append(
                        {
                            "army": army,
                            "position": entry["position"],
                            "column": entry["column"],
                            "row": entry["row"],
                            "speed": entry["speed"],
                        }
                    )
                engine = ArenaEngine()
                engine.start_arena_battle(battle_layout, targeting_mode=targeting_mode)
                while True:
                    engine.tick(0.016)
                    alive = {
                        ctx.team
                        for ctx in engine._armies.values()
                        if ctx.army.current_troop_count > 0
                    }
                    if len(alive) <= 1:
                        break
                winner = next(iter(alive)) if alive else "None"
                results[winner] = results.get(winner, 0) + 1
            window = self.window()
            if window is not None and hasattr(window, "update_arena_figures"):
                window.update_arena_figures(results)
            return

        window = self.window()
        if window is None:
            return
        runs = window.runs_spin.value()
        workers = window.workers_spin.value()
        window.status.setText("Running arena batch...")
        window.progress.setRange(0, runs)
        window.progress.setValue(0)
        self.run_batch_btn.setEnabled(False)
        worker = ArenaBatchWorker(layout_entries, runs, workers, str(targeting_mode))
        self._batch_worker = worker
        worker.progress_update.connect(
            lambda d, t: (window.progress.setMaximum(t), window.progress.setValue(d))
        )
        worker.finished_dict.connect(lambda res: window.update_arena_figures(res))

        def _finished() -> None:
            window.progress.setValue(0)
            window.status.setText("Ready")
            self.run_batch_btn.setEnabled(True)
            self._batch_worker = None
            worker.deleteLater()

        worker.finished.connect(_finished)
        worker.start()

    def _on_engine_state(self, name: str, state: dict) -> None:
        """Update bars in response to engine state broadcasts."""
        icon = self._icons.get(name)
        if not icon:
            return
        ctx = self.engine._armies.get(name)
        if not ctx:
            return
        army = ctx.army
        initial = max(1.0, army.unit.initial_count)
        icon.set_health(army.current_troop_count / initial)
        rage = state.get("rage", army.current_rage)
        icon.set_rage(rage / 1000.0)

    def _on_timer_tick(self) -> None:
        """Advance the arena battle and update icon positions."""

        now = time.perf_counter()
        dt = now - self._last_tick
        self._last_tick = now
        sim_dt = dt * self._speed_multiplier
        self.engine.tick(sim_dt)
        self._battle_time += sim_dt
        self._update_time_label()
        for name, icon in list(self._icons.items()):
            ctx = self.engine._armies.get(name)
            if ctx is None or ctx.army.current_troop_count <= 0:
                self.scene.removeItem(icon)
                self._icons.pop(name, None)
                continue
            x, y = ctx.position
            icon.setPos(x, y)
        window = self.window()
        if window is not None and hasattr(window, "update_arena_reports"):
            window.update_arena_reports()
        alive = {
            ctx.team
            for ctx in self.engine._armies.values()
            if ctx.army.current_troop_count > 0
        }
        if len(alive) <= 1:
            self._timer.stop()
            self._running = False
            self.run_btn.setEnabled(True)
            for item in self._slot_items.values():
                item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)
            summary = []
            for info in self._slot_army.values():
                if not info:
                    continue
                army = info["army"]
                cfg = info.get("config", {})
                team = info.get("team", "red")
                summary.append(build_army_skill_summary(army, cfg, team))
            if window is not None and hasattr(window, "update_arena_figures"):
                window.update_arena_figures(summary)

    def _refresh_arena(self) -> None:
        """Clear armies and reset slot occupancy."""

        self.scene.clear()
        self._icons.clear()
        self._slot_items.clear()
        self._slot_army.clear()
        self._draw_navmesh()
        self.report_builder = BattlefieldReportBuilder()
        self.engine.reset(report_builder=self.report_builder)
        self._timer.stop()
        self._running = False
        self.run_btn.setEnabled(True)
        self._battle_time = 0.0
        self._speed_multiplier = 1.0
        self.speed_btn.setText("Speed 1x")
        self._update_time_label()

        radius = min(self._cell_w, self._cell_h) * 0.15
        for team, coords in self.slot_coords.items():
            for idx, (x, y) in enumerate(coords):
                item = SlotItem(team, idx, radius, self._slot_clicked, self._cell_w, self._cell_h)
                item.setPos(x, y)
                self.scene.addItem(item)
                self._slot_items[(team, idx)] = item
                self._slot_army[(team, idx)] = None

    def _toggle_speed(self) -> None:
        """Cycle through speed multipliers for the arena simulation."""

        speeds = [1.0, 2.0, 4.0, 6.0]
        idx = speeds.index(self._speed_multiplier)
        self._speed_multiplier = speeds[(idx + 1) % len(speeds)]
        self.speed_btn.setText(f"Speed {int(self._speed_multiplier)}x")

    def _update_time_label(self) -> None:
        """Display the elapsed battle time in minutes and seconds."""

        minutes = int(self._battle_time // 60)
        seconds = int(self._battle_time % 60)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")

    # ------------------------------------------------------------------
    # Navigation mesh helpers
    # ------------------------------------------------------------------
    def _draw_navmesh(self) -> None:
        """Render the arena background and keep it scaled to the view."""

        if hasattr(self, "_background") and not self._background.isNull():
            scaled = self._background.scaled(
                int(self.view.sceneRect().width()),
                int(self.view.sceneRect().height()),
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            bg_item = self.scene.addPixmap(scaled)
            bg_item.setZValue(-2)

        self.view.fitInView(
            self.view.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        """Keep the entire arena visible when the widget is resized."""
        super().resizeEvent(event)
        self.view.fitInView(
            self.view.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

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
        "unrevivable_victory_distribution.png",
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
            # Use a context manager so file handles are closed immediately.
            # Leaving images open prevented them from being overwritten on
            # subsequent runs which caused the simulator to crash when run
            # multiple times in the same session.
            with Image.open(path) as img:
                if img.width > max_width or img.height > max_height:
                    ratio = min(max_width / img.width, max_height / img.height)
                    img = img.resize(
                        (int(img.width * ratio), int(img.height * ratio)),
                        Image.LANCZOS,
                    )
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
        self.seed_target: SeedTarget | None = None
        self.seed_display: QtWidgets.QLabel | None = None
        self.hero_cooldowns_enabled: bool = True
        self.plugin_cooldowns_enabled: bool = True
        self.gem_cooldowns_enabled: bool = True
        self.mount_cooldowns_enabled: bool = True
        self._dynamic_unrevivable_settings = dynamic_unrevivable_config.get_settings()
        self._troop_scalar_multiplier = troop_scalar_config.get_multiplier()
        main_layout = self._init_tabs()
        self._init_status_controls(main_layout)
        self.pdf_layout = load_pdf_layout()
        self._last_setup_data: list[dict] | None = None
        self._last_simulation_payload: dict[str, Any] | None = None

    def open_star_overlay_tuner(self) -> None:
        """Open the star overlay debug dialog."""
        dlg = StarOverlayDebugDialog(self)
        dlg.exec()

    def open_pdf_layout_tool(self) -> None:
        """Open the PDF layout configuration dialog."""
        dlg = PDFLayoutDialog(self)
        if dlg.exec():
            self.pdf_layout = load_pdf_layout()

    def open_dynamic_unrevivable_tool(self) -> None:
        """Open the dynamic unrevivable configuration dialog."""
        dlg = DynamicUnrevivableDialog(self)
        dlg.settings_applied.connect(self._on_dynamic_unrevivable_settings_changed)
        dlg.exec()

    def open_troop_scalar_tool(self) -> None:
        """Open the troop scalar multiplier configuration dialog."""
        dlg = TroopScalarDialog(self)
        dlg.multiplier_applied.connect(self._on_troop_scalar_multiplier_changed)
        dlg.exec()

    def _on_dynamic_unrevivable_settings_changed(self) -> None:
        self._dynamic_unrevivable_settings = dynamic_unrevivable_config.get_settings()

    def _on_troop_scalar_multiplier_changed(self, value: float) -> None:
        self._troop_scalar_multiplier = float(value)

    def _on_hero_cooldowns_toggled(self, checked: bool) -> None:
        self.hero_cooldowns_enabled = bool(checked)

    def _on_plugin_cooldowns_toggled(self, checked: bool) -> None:
        self.plugin_cooldowns_enabled = bool(checked)

    def _on_gem_cooldowns_toggled(self, checked: bool) -> None:
        self.gem_cooldowns_enabled = bool(checked)

    def _on_mount_cooldowns_toggled(self, checked: bool) -> None:
        self.mount_cooldowns_enabled = bool(checked)

    def _open_gear_dialog(self, frame: ArmyFrame) -> None:
        hero_names = [frame.hero1_combo.currentText(), frame.hero2_combo.currentText()]
        dlg = GearSelectionDialog(hero_names, frame.get_gear_config(), self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            frame.set_gear_config(dlg.result())

    def _init_tabs(self) -> QtWidgets.QVBoxLayout:
        """Create the central widget and all tabs."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)

        # Remember the directory last used when loading/saving setups
        self.last_setup_dir = os.path.join(os.path.dirname(__file__), "setups")

        # --- Army Setup tab ---
        self.setup_tab = QtWidgets.QWidget()
        setup_layout = QtWidgets.QVBoxLayout(self.setup_tab)

        controls = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self.run_simulation)
        controls.addWidget(self.run_btn)
        save_btn = QtWidgets.QPushButton("Save Setup")
        save_btn.clicked.connect(self.save_setup)
        controls.addWidget(save_btn)
        load_btn = QtWidgets.QPushButton("Load Setup")
        load_btn.clicked.connect(self.load_setup)
        controls.addWidget(load_btn)
        swap_btn = QtWidgets.QPushButton("Swap Armies")
        swap_btn.clicked.connect(self.swap_armies)
        controls.addWidget(swap_btn)
        duplicate_btn = QtWidgets.QToolButton()
        duplicate_btn.setText("Duplicate Army")
        dup_menu = QtWidgets.QMenu(duplicate_btn)
        dup1_action = dup_menu.addAction("1 → 2")
        dup1_action.triggered.connect(lambda: self.duplicate_army(1, 2))
        dup2_action = dup_menu.addAction("2 → 1")
        dup2_action.triggered.connect(lambda: self.duplicate_army(2, 1))
        duplicate_btn.setMenu(dup_menu)
        duplicate_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        controls.addWidget(duplicate_btn)
        debug_btn = QtWidgets.QToolButton()
        debug_btn.setText("Debug")
        dbg_menu = QtWidgets.QMenu(debug_btn)
        pdf_action = dbg_menu.addAction("PDF Layout")
        pdf_action.triggered.connect(self.open_pdf_layout_tool)
        dynamic_action = dbg_menu.addAction("Dynamic Unrevivable…")
        dynamic_action.triggered.connect(self.open_dynamic_unrevivable_tool)
        troop_scalar_action = dbg_menu.addAction("Change Troop Scalar…")
        troop_scalar_action.triggered.connect(self.open_troop_scalar_tool)
        cooldowns_menu = dbg_menu.addMenu("Cooldowns")
        hero_cooldowns_action = cooldowns_menu.addAction("Hero cooldowns")
        hero_cooldowns_action.setCheckable(True)
        hero_cooldowns_action.setChecked(self.hero_cooldowns_enabled)
        hero_cooldowns_action.toggled.connect(self._on_hero_cooldowns_toggled)

        plugin_cooldowns_action = cooldowns_menu.addAction("Plugin cooldowns")
        plugin_cooldowns_action.setCheckable(True)
        plugin_cooldowns_action.setChecked(self.plugin_cooldowns_enabled)
        plugin_cooldowns_action.toggled.connect(self._on_plugin_cooldowns_toggled)

        gem_cooldowns_action = cooldowns_menu.addAction("Gem cooldowns")
        gem_cooldowns_action.setCheckable(True)
        gem_cooldowns_action.setChecked(self.gem_cooldowns_enabled)
        gem_cooldowns_action.toggled.connect(self._on_gem_cooldowns_toggled)

        mount_cooldowns_action = cooldowns_menu.addAction("Mount cooldowns")
        mount_cooldowns_action.setCheckable(True)
        mount_cooldowns_action.setChecked(self.mount_cooldowns_enabled)
        mount_cooldowns_action.toggled.connect(self._on_mount_cooldowns_toggled)
        star_action = dbg_menu.addAction("Star Layout")
        star_action.triggered.connect(self.open_star_overlay_tuner)
        debug_btn.setMenu(dbg_menu)
        debug_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        controls.addWidget(debug_btn)
        seed_btn = QtWidgets.QToolButton()
        seed_btn.setText("Seed…")
        seed_btn.clicked.connect(self._choose_seed_target)
        controls.addWidget(seed_btn)
        self.seed_display = QtWidgets.QLabel()
        self.seed_display.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.NoTextInteraction
        )
        controls.addWidget(self.seed_display)
        self._update_seed_display()
        controls.addStretch()
        setup_layout.addLayout(controls)

        armies_row = QtWidgets.QHBoxLayout()
        self.army1_frame = ArmyFrame(1)
        self.army2_frame = ArmyFrame(2)
        self.army1_frame.set_peer_frames([self.army2_frame])
        self.army2_frame.set_peer_frames([self.army1_frame])
        self.army1_frame.gear_btn.clicked.connect(
            lambda: self._open_gear_dialog(self.army1_frame)
        )
        self.army2_frame.gear_btn.clicked.connect(
            lambda: self._open_gear_dialog(self.army2_frame)
        )
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

        # 1v1 tabs
        self.tabs.addTab(self.setup_tab, "Army Setup")

        # --- Battlefield tab ---
        self.battlefield_tab = BattlefieldTab()

        # --- Arena tab ---
        self.arena_tab = ArenaTab()

        # --- Battlefield Reports tab ---
        self.battlefield_report_tab = QtWidgets.QWidget()
        bf_layout = QtWidgets.QVBoxLayout(self.battlefield_report_tab)

        self.bf_report_list = QtWidgets.QListWidget()
        self.bf_report_list.currentItemChanged.connect(
            self._display_selected_bf_report
        )
        bf_layout.addWidget(self.bf_report_list)

        self.bf_toggle_report_view_btn = QtWidgets.QPushButton(
            "Show Text Report"
        )
        self.bf_toggle_report_view_btn.setCheckable(True)
        self.bf_toggle_report_view_btn.toggled.connect(
            self._toggle_bf_report_view
        )
        bf_layout.addWidget(
            self.bf_toggle_report_view_btn,
            alignment=QtCore.Qt.AlignmentFlag.AlignLeft,
        )

        self.bf_report_stack = QtWidgets.QStackedWidget()

        bf_fixed_font = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        )

        self.bf_output_tree = QtWidgets.QTreeWidget()
        self.bf_output_tree.setHeaderHidden(True)
        self.bf_output_tree.setFont(bf_fixed_font)
        self.bf_output_tree.setStyleSheet(
            "QTreeWidget { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.bf_report_stack.addWidget(self.bf_output_tree)

        self.bf_output_text = QtWidgets.QTextEdit()
        self.bf_output_text.setReadOnly(True)
        self.bf_output_text.setFont(bf_fixed_font)
        self.bf_output_text.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.bf_report_stack.addWidget(self.bf_output_text)

        bf_layout.addWidget(self.bf_report_stack)

        # --- Arena Reports tab ---
        self.arena_report_tab = QtWidgets.QWidget()
        ar_layout = QtWidgets.QVBoxLayout(self.arena_report_tab)

        self.ar_report_list = QtWidgets.QListWidget()
        self.ar_report_list.currentItemChanged.connect(
            self._display_selected_ar_report
        )
        ar_layout.addWidget(self.ar_report_list)

        ar_btn_layout = QtWidgets.QHBoxLayout()
        self.ar_toggle_report_view_btn = QtWidgets.QPushButton(
            "Show Text Report"
        )
        self.ar_toggle_report_view_btn.setCheckable(True)
        self.ar_toggle_report_view_btn.toggled.connect(
            self._toggle_ar_report_view
        )
        ar_btn_layout.addWidget(self.ar_toggle_report_view_btn)
        self.ar_clear_reports_btn = QtWidgets.QPushButton("Clear Reports")
        self.ar_clear_reports_btn.clicked.connect(self._clear_arena_reports)
        ar_btn_layout.addWidget(self.ar_clear_reports_btn)
        ar_btn_layout.addStretch()
        ar_layout.addLayout(ar_btn_layout)

        self.ar_report_stack = QtWidgets.QStackedWidget()

        ar_fixed_font = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        )

        self.ar_output_tree = QtWidgets.QTreeWidget()
        self.ar_output_tree.setHeaderHidden(True)
        self.ar_output_tree.setFont(ar_fixed_font)
        self.ar_output_tree.setStyleSheet(
            "QTreeWidget { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.ar_report_stack.addWidget(self.ar_output_tree)

        self.ar_output_text = QtWidgets.QTextEdit()
        self.ar_output_text.setReadOnly(True)
        self.ar_output_text.setFont(ar_fixed_font)
        self.ar_output_text.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.ar_report_stack.addWidget(self.ar_output_text)

        ar_layout.addWidget(self.ar_report_stack)

        # --- Arena Figures tab ---
        self.arena_figures_tab = QtWidgets.QWidget()
        ar_fig_layout = QtWidgets.QVBoxLayout(self.arena_figures_tab)
        self.arena_fig_stack = QtWidgets.QStackedWidget()
        self.arena_fig_label = QtWidgets.QLabel("Run Batch to generate figures")
        self.arena_fig_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.arena_fig_stack.addWidget(self.arena_fig_label)
        self.arena_fig_scroll = QtWidgets.QScrollArea()
        self.arena_fig_scroll.setWidgetResizable(True)
        self.arena_fig_scroll.setStyleSheet("background: transparent;")
        self.arena_fig_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.arena_fig_summary = QtWidgets.QWidget()
        self.arena_fig_summary.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        bg_path = os.path.join(
            os.path.dirname(__file__), "Icons", "ArenaSummaryBackground.png"
        ).replace("\\", "/")
        self.arena_fig_summary.setStyleSheet(
            f"background-image: url({bg_path});"
            "background-repeat: no-repeat;"
            "background-position: center;"
        )
        self.arena_fig_summary_layout = QtWidgets.QGridLayout(self.arena_fig_summary)
        self.arena_fig_scroll.setWidget(self.arena_fig_summary)
        self.arena_fig_stack.addWidget(self.arena_fig_scroll)
        ar_fig_layout.addWidget(self.arena_fig_stack)

        # --- Report tab ---
        self.report_tab = QtWidgets.QWidget()
        report_layout = QtWidgets.QVBoxLayout(self.report_tab)

        report_controls = QtWidgets.QHBoxLayout()
        self.toggle_report_view_btn = QtWidgets.QPushButton("Show Text Report")
        self.toggle_report_view_btn.setCheckable(True)
        self.toggle_report_view_btn.toggled.connect(self._toggle_report_view)
        report_controls.addWidget(self.toggle_report_view_btn)
        clear_report_btn = QtWidgets.QPushButton("Clear Output")
        clear_report_btn.clicked.connect(self._clear_report)
        report_controls.addWidget(clear_report_btn)
        report_controls.addStretch()
        report_layout.addLayout(report_controls)

        self.report_stack = QtWidgets.QStackedWidget()

        fixed_font = QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        )

        self.output_tree = QtWidgets.QTreeWidget()
        self.output_tree.setHeaderHidden(True)
        self.output_tree.setFont(fixed_font)
        self.output_tree.setStyleSheet(
            "QTreeWidget { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.report_stack.addWidget(self.output_tree)

        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(fixed_font)
        self.output_text.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #ffffff; "
            "border: 1px solid #444444; }"
        )
        self.report_stack.addWidget(self.output_text)

        report_layout.addWidget(self.report_stack)
        self.tabs.addTab(self.report_tab, "Report")

        # --- Figures tab ---
        self.figures_tab = QtWidgets.QWidget()
        fig_layout = QtWidgets.QVBoxLayout(self.figures_tab)
        fig_controls = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QToolButton()
        export_btn.setText("Export")
        export_menu = QtWidgets.QMenu(export_btn)
        export_report_action = QtGui.QAction("Export Report", self)
        export_report_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+R"))
        export_report_action.triggered.connect(self.export_report)
        export_fig_action = QtGui.QAction("Export Figures", self)
        export_fig_action.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        export_fig_action.triggered.connect(self.export_figures)
        export_summary_action = QtGui.QAction("Export Summary Image", self)
        export_summary_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+E"))
        export_summary_action.triggered.connect(self.export_summary_image)
        export_html_action = QtGui.QAction("Export Overall Performance HTML", self)
        export_html_action.setShortcut(QtGui.QKeySequence("Ctrl+Alt+E"))
        export_html_action.triggered.connect(self.export_summary_html)
        export_html_sample_action = QtGui.QAction(
            "Export Overall Performance & Sample Battle HTML", self
        )
        export_html_sample_action.setShortcut(
            QtGui.QKeySequence("Ctrl+Alt+Shift+E")
        )
        export_html_sample_action.triggered.connect(
            self.export_summary_with_sample_html
        )
        export_html_sample_summary_action = QtGui.QAction(
            "Export Overall Performance & Sample Battle Summary HTML", self
        )
        export_html_sample_summary_action.setShortcut(
            QtGui.QKeySequence("Ctrl+Alt+Shift+S")
        )
        export_html_sample_summary_action.triggered.connect(
            self.export_summary_with_sample_summary_html
        )
        export_pdf_action = QtGui.QAction("Export PDF", self)
        export_pdf_action.triggered.connect(self.export_pdf)
        for act in (
            export_report_action,
            export_fig_action,
            export_summary_action,
            export_html_action,
            export_html_sample_action,
            export_html_sample_summary_action,
            export_pdf_action,
        ):
            self.addAction(act)
            export_menu.addAction(act)
        export_btn.setMenu(export_menu)
        export_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        fig_controls.addWidget(export_btn)
        clear_fig_btn = QtWidgets.QPushButton("Clear Output")
        clear_fig_btn.clicked.connect(self._clear_figures)
        fig_controls.addWidget(clear_fig_btn)
        fig_controls.addStretch()
        fig_layout.addLayout(fig_controls)

        self.hist_container = QtWidgets.QWidget()
        self.hist_scroll = QtWidgets.QScrollArea()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setWidget(self.hist_container)
        fig_layout.addWidget(self.hist_scroll)
        self.tabs.addTab(self.figures_tab, "Figures")

        # --- Skill breakdown tab ---
        self.skill_breakdown_tab = QtWidgets.QWidget()
        sb_layout = QtWidgets.QVBoxLayout(self.skill_breakdown_tab)
        self.skill_breakdown_stack = QtWidgets.QStackedWidget()
        self.skill_breakdown_placeholder = QtWidgets.QLabel()
        self.skill_breakdown_placeholder.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.skill_breakdown_placeholder.setWordWrap(True)
        self.skill_breakdown_stack.addWidget(self.skill_breakdown_placeholder)
        self.skill_breakdown_scroll = QtWidgets.QScrollArea()
        self.skill_breakdown_scroll.setWidgetResizable(True)
        self.skill_breakdown_scroll.setStyleSheet("background: transparent;")
        self.skill_breakdown_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.skill_breakdown_widget = QtWidgets.QWidget()
        self.skill_breakdown_widget.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_StyledBackground, True
        )
        sb_bg_path = os.path.join(
            os.path.dirname(__file__),
            "Icons",
            "ArenaSummaryBackground.png",
        ).replace("\\", "/")
        self.skill_breakdown_widget.setStyleSheet(
            f"background-image: url({sb_bg_path});"
            "background-repeat: no-repeat;"
            "background-position: center;"
        )
        self.skill_breakdown_layout = QtWidgets.QGridLayout(self.skill_breakdown_widget)
        self.skill_breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self.skill_breakdown_layout.setSpacing(0)
        self.skill_breakdown_scroll.setWidget(self.skill_breakdown_widget)
        self.skill_breakdown_stack.addWidget(self.skill_breakdown_scroll)
        sb_layout.addWidget(self.skill_breakdown_stack)
        self.tabs.addTab(self.skill_breakdown_tab, "Skill Breakdowns")
        self._skill_breakdown_default_message = (
            "Run Simulation to view skill breakdowns"
        )
        self._set_skill_breakdown_message(self._skill_breakdown_default_message)

        # Multi-army tabs
        self.tabs.addTab(self.battlefield_tab, "Battlefield")
        self.tabs.addTab(self.battlefield_report_tab, "Battlefield Reports")
        self.tabs.addTab(self.arena_tab, "Arena")
        self.tabs.addTab(self.arena_report_tab, "Arena Reports")
        self.tabs.addTab(self.arena_figures_tab, "Arena Figures")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        return main_layout

    def _choose_seed_target(self) -> None:
        """Open the seed outcome dialog and store the selection."""

        army1_name = self.army1_frame.name_edit.text() or "Army 1"
        army2_name = self.army2_frame.name_edit.text() or "Army 2"
        dlg = SeedOutcomeDialog(self, army1_name, army2_name, self.seed_target)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            target = dlg.target()
            self.seed_target = dict(target) if target else None
            self._update_seed_display()

    def _update_seed_display(self) -> None:
        """Refresh the text next to the seed selection button."""

        if not self.seed_display:
            return
        if not self.seed_target:
            self.seed_display.setText("Seed: Auto")
            return
        winner = self.seed_target.get("winner", 1)
        remaining = int(self.seed_target.get("remaining", 0))
        formatted = f"{remaining:,}".replace(",", "\u202f")
        display = f"Seed: Army\u202f{winner}, {formatted}"
        rounds_val = self.seed_target.get("rounds")
        if isinstance(rounds_val, (int, float)):
            rounds_int = int(round(float(rounds_val)))
            tolerance_val = self.seed_target.get("round_tolerance", 0)
            tolerance_int = int(round(float(tolerance_val))) if tolerance_val is not None else 0
            if tolerance_int > 0:
                display += f" (Rounds: {rounds_int}\u00a0\u00b1\u00a0{tolerance_int})"
            else:
                display += f" (Rounds: {rounds_int})"
        self.seed_display.setText(display)

    def _init_status_controls(self, main_layout: QtWidgets.QVBoxLayout) -> None:
        """Create status label, progress bar and run options."""
        self.status = QtWidgets.QLabel("Ready")
        main_layout.addWidget(self.status)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        main_layout.addWidget(self.progress)

        self.opts_widget = QtWidgets.QWidget()
        opts_layout = QtWidgets.QHBoxLayout(self.opts_widget)
        main_layout.addWidget(self.opts_widget)

        opts_layout.addWidget(QtWidgets.QLabel("Additional Runs:"))
        self.runs_spin = QtWidgets.QSpinBox()
        self.runs_spin.setRange(1, 10000)
        self.runs_spin.setValue(300)
        opts_layout.addWidget(self.runs_spin)

        opts_layout.addWidget(QtWidgets.QLabel("Worker Processes:"))
        self.workers_spin = QtWidgets.QSpinBox()
        cpu_count = os.cpu_count() or 1
        self.workers_spin.setRange(1, cpu_count)
        self.workers_spin.setValue(cpu_count)
        opts_layout.addWidget(self.workers_spin)

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

    def duplicate_army(self, source: int, target: int) -> None:
        if source == target or source not in {1, 2} or target not in {1, 2}:
            return
        src_frame = self.army1_frame if source == 1 else self.army2_frame
        dst_frame = self.army1_frame if target == 1 else self.army2_frame
        cfg = src_frame.build_config()
        dst_frame.populate_from_config(cfg)
        old_widget = self.hist_scroll.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()
        self.hist_container = QtWidgets.QWidget()
        self.hist_scroll.setWidget(self.hist_container)
        self.status.setText(f"Army {source} duplicated to Army {target}")

    def swap_armies(self) -> None:
        cfg1 = self.army1_frame.build_config()
        cfg2 = self.army2_frame.build_config()
        self.army1_frame.populate_from_config(cfg2)
        self.army2_frame.populate_from_config(cfg1)
        old_widget = self.hist_scroll.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()
        self.hist_container = QtWidgets.QWidget()
        self.hist_scroll.setWidget(self.hist_container)
        self._set_skill_breakdown_message(self._skill_breakdown_default_message)
        self.status.setText("Armies swapped")

    def _clear_report(self) -> None:
        self.output_text.clear()
        self.output_tree.clear()

    def _clear_figures(self) -> None:
        old_widget = self.hist_scroll.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()
        self.hist_container = QtWidgets.QWidget()
        self.hist_scroll.setWidget(self.hist_container)
        self._set_skill_breakdown_message(self._skill_breakdown_default_message)

    def _collect_histogram_images(self) -> list[str]:
        base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
        if not os.path.isdir(base_hist_dir):
            return []
        paths = []
        for fname in sorted(os.listdir(base_hist_dir)):
            if fname.lower().endswith(".png"):
                full = os.path.join(base_hist_dir, fname)
                if os.path.isfile(full):
                    paths.append(full)
        return paths

    def _clear_skill_breakdown_layout(self) -> None:
        """Remove all widgets from the skill breakdown layout."""

        layout = getattr(self, "skill_breakdown_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _set_skill_breakdown_message(self, message: str) -> None:
        """Show ``message`` in the skill breakdown tab."""

        if not hasattr(self, "skill_breakdown_placeholder"):
            return
        self._clear_skill_breakdown_layout()
        self.skill_breakdown_placeholder.setText(message)
        self.skill_breakdown_stack.setCurrentWidget(self.skill_breakdown_placeholder)

    def update_skill_breakdowns(self, summary: list[dict[str, Any]]) -> None:
        """Render hero skill statistics for the most recent simulation."""

        if not summary:
            self._set_skill_breakdown_message(self._skill_breakdown_default_message)
            return

        self._clear_skill_breakdown_layout()
        max_healed = max((entry.get("healed", 0) for entry in summary), default=1)
        max_kills = max((entry.get("kills", 0) for entry in summary), default=1)
        red_entries = [e for e in summary if e.get("team", "red") == "red"]
        blue_entries = [e for e in summary if e.get("team", "blue") == "blue"]

        self.skill_breakdown_layout.addWidget(ArenaStatsHeader(), 0, 0)
        for row, (red, blue) in enumerate(zip_longest(red_entries, blue_entries), start=1):
            row_widget = ArenaStatsRow(red, blue, max_healed, max_kills)
            self.skill_breakdown_layout.addWidget(row_widget, row, 0)

        self.skill_breakdown_stack.setCurrentWidget(self.skill_breakdown_scroll)

    def _toggle_report_view(self, checked: bool) -> None:
        if checked:
            self.report_stack.setCurrentWidget(self.output_text)
            self.toggle_report_view_btn.setText("Show Round View")
        else:
            self.report_stack.setCurrentWidget(self.output_tree)
            self.toggle_report_view_btn.setText("Show Text Report")

    def _toggle_bf_report_view(self, checked: bool) -> None:
        if checked:
            self.bf_report_stack.setCurrentWidget(self.bf_output_text)
            self.bf_toggle_report_view_btn.setText("Show Round View")
        else:
            self.bf_report_stack.setCurrentWidget(self.bf_output_tree)
            self.bf_toggle_report_view_btn.setText("Show Text Report")

    def _toggle_ar_report_view(self, checked: bool) -> None:
        if checked:
            self.ar_report_stack.setCurrentWidget(self.ar_output_text)
            self.ar_toggle_report_view_btn.setText("Show Round View")
        else:
            self.ar_report_stack.setCurrentWidget(self.ar_output_tree)
            self.ar_toggle_report_view_btn.setText("Show Text Report")

    def update_battlefield_reports(self) -> None:
        """Populate the battlefield report list from the engine."""
        builder = getattr(self.battlefield_tab, "report_builder", None)
        if not builder:
            return

        # Preserve the currently selected report so the list doesn't reset while
        # the battlefield engine is running.  The engine refreshes this list
        # every tick which previously cleared the selection, making it
        # impossible to read any report.
        current_item = self.bf_report_list.currentItem()
        current_key = (
            current_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if current_item is not None
            else None
        )

        # Determine if the list actually changed compared to the last refresh
        existing_keys = [
            self.bf_report_list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            for i in range(self.bf_report_list.count())
        ]
        new_keys = list(builder.get_reports().keys())
        if existing_keys == new_keys:
            return

        self.bf_report_list.clear()
        for key in new_keys:
            atk, dfd = key
            item = QtWidgets.QListWidgetItem(f"{atk} vs {dfd}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.bf_report_list.addItem(item)
            if key == current_key:
                self.bf_report_list.setCurrentItem(item)

    def update_arena_reports(self) -> None:
        """Populate the arena report list from the arena engine."""
        builder = getattr(self.arena_tab, "report_builder", None)
        if not builder:
            return

        current_item = self.ar_report_list.currentItem()
        current_key = (
            current_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if current_item is not None
            else None
        )

        existing_keys = [
            self.ar_report_list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            for i in range(self.ar_report_list.count())
        ]
        new_keys = list(builder.get_reports().keys())
        if existing_keys == new_keys:
            return

        self.ar_report_list.clear()
        for key in new_keys:
            atk, dfd = key
            item = QtWidgets.QListWidgetItem(f"{atk} vs {dfd}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.ar_report_list.addItem(item)
            if key == current_key:
                self.ar_report_list.setCurrentItem(item)

    def _clear_arena_reports(self) -> None:
        """Clear all arena battle reports."""
        builder = getattr(self.arena_tab, "report_builder", None)
        if builder:
            builder.clear_all()
        self.ar_report_list.clear()
        self.ar_output_tree.clear()
        self.ar_output_text.clear()

    def update_arena_figures(self, results: dict[str, int] | list[dict[str, Any]]) -> None:
        """Display arena outcome information."""

        if not results:
            return

        if isinstance(results, dict):
            base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
            os.makedirs(base_hist_dir, exist_ok=True)
            path = os.path.join(base_hist_dir, "arena_victory_distribution.png")
            order = ["blue", "red"]
            color_map = {"blue": "#0000ff", "red": "#ff0000"}
            labels: list[str] = []
            sizes: list[int] = []
            colors: list[str] = []
            for team in order:
                count = results.get(team, 0)
                if count:
                    labels.append(team.capitalize())
                    sizes.append(count)
                    colors.append(color_map[team])
            for team, count in results.items():
                if team not in order and count:
                    labels.append(team.capitalize())
                    sizes.append(count)
                    colors.append("#808080")
            if not sizes:
                return
            fig, ax = plt.subplots()
            ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%")
            ax.set_title("Arena Victory Distribution")
            fig.savefig(path)
            plt.close(fig)
            self.arena_fig_label.setPixmap(QtGui.QPixmap(path))
            self.arena_fig_stack.setCurrentWidget(self.arena_fig_label)
            return

        # Otherwise render per-army summary after a normal run
        for i in reversed(range(self.arena_fig_summary_layout.count())):
            item = self.arena_fig_summary_layout.takeAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        red_entries = [e for e in results if e.get("team", "red") == "red"]
        blue_entries = [e for e in results if e.get("team", "blue") == "blue"]
        max_healed = max((e.get("healed", 0) for e in results), default=1)
        max_kills = max((e.get("kills", 0) for e in results), default=1)

        self.arena_fig_summary_layout.addWidget(ArenaStatsHeader(), 0, 0)
        for row, (red, blue) in enumerate(zip_longest(red_entries, blue_entries), start=1):
            row_widget = ArenaStatsRow(red, blue, max_healed, max_kills)
            self.arena_fig_summary_layout.addWidget(row_widget, row, 0)

        self.arena_fig_stack.setCurrentWidget(self.arena_fig_scroll)

    def _display_selected_bf_report(
        self, current: QtWidgets.QListWidgetItem | None
    ) -> None:
        if current is None:
            self.bf_output_tree.clear()
            self.bf_output_text.clear()
            return
        key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        builder = getattr(self.battlefield_tab, "report_builder", None)
        if not builder:
            return
        rounds = builder.get_rounds().get(key, [])
        text = builder.get_reports().get(key, "")

        # Replace only whole-round lines to avoid nested substitutions
        if text:
            lines = text.splitlines()
            for idx, line in enumerate(lines):
                stripped = line.strip()
                for r in rounds:
                    gr = r.get("defender_global_round")
                    if gr is not None and stripped == f"Round {r['round']}":
                        lines[idx] = f"Round {r['round']} (Defender Round {gr})"
                        break
            text = "\n".join(lines)

        self.bf_output_text.setPlainText(text)
        self._populate_round_tree(rounds, tree=self.bf_output_tree)

    def _display_selected_ar_report(
        self, current: QtWidgets.QListWidgetItem | None
    ) -> None:
        if current is None:
            self.ar_output_tree.clear()
            self.ar_output_text.clear()
            return
        key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        builder = getattr(self.arena_tab, "report_builder", None)
        if not builder:
            return
        rounds = builder.get_rounds().get(key, [])
        text = builder.get_reports().get(key, "")

        if text:
            lines = text.splitlines()
            for idx, line in enumerate(lines):
                stripped = line.strip()
                for r in rounds:
                    gr = r.get("defender_global_round")
                    if gr is not None and stripped == f"Round {r['round']}":
                        lines[idx] = f"Round {r['round']} (Defender Round {gr})"
                        break
            text = "\n".join(lines)

        self.ar_output_text.setPlainText(text)
        self._populate_round_tree(rounds, tree=self.ar_output_tree)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.battlefield_report_tab:
            self.update_battlefield_reports()
        if widget is self.arena_report_tab:
            self.update_arena_reports()
        visible_tabs = {
            self.setup_tab,
            self.report_tab,
            self.figures_tab,
            self.arena_tab,
            self.arena_report_tab,
            self.arena_figures_tab,
        }
        visible = widget in visible_tabs
        self.status.setVisible(visible)
        self.progress.setVisible(visible)
        self.opts_widget.setVisible(visible)

    def export_report(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Report",
            self.last_setup_dir,
            "Text Files (*.txt)",
        )
        if file_path:
            self.last_setup_dir = os.path.dirname(file_path)
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.write(self.output_text.toPlainText())
                self.status.setText(f"Report exported to {os.path.basename(file_path)}")
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to export report: {exc}"
                )

    def export_figures(self) -> None:
        image_files = [
            "own_remaining_troops.png",
            "enemy_remaining_troops.png",
            "rounds_to_battle_end.png",
            "victory_distribution.png",
            "unrevivable_victory_distribution.png",
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
    def _generate_preview_and_hist_pixmaps(self) -> tuple[QtGui.QPixmap | None, dict[str, QtGui.QPixmap]]:
        """Return the army preview pixmap and histogram pixmaps."""

        image_files = [
            "own_remaining_troops.png",
            "enemy_remaining_troops.png",
            "rounds_to_battle_end.png",
            "victory_distribution.png",
            "unrevivable_victory_distribution.png",
        ]
        base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
        hist_pixmaps: dict[str, QtGui.QPixmap] = {}
        for fname in image_files:
            path = os.path.join(base_hist_dir, fname)
            if os.path.exists(path):
                pm = QtGui.QPixmap(path)
                if pm.isNull():
                    continue
                pm = make_transparent(pm)
                hist_pixmaps[os.path.splitext(fname)[0]] = pm
        if not hist_pixmaps:
            return None, {}

        scale = 5

        def render_preview(widget: QtWidgets.QWidget) -> QtGui.QPixmap:
            pix = QtGui.QPixmap(widget.size())
            pix.fill(QtCore.Qt.GlobalColor.transparent)
            flags = QtWidgets.QWidget.RenderFlag.DrawChildren
            widget.render(pix, QtCore.QPoint(), QtGui.QRegion(), flags)
            return pix.scaled(
                widget.width() * scale,
                widget.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )

        p1 = render_preview(self.army1_frame.preview_widget)
        p2 = render_preview(self.army2_frame.preview_widget)
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
            padding = vs_pix.width() // 2
            extra_after_vs = 1700
            left_space = p1.width() + padding
            right_space = p2.width() + padding + extra_after_vs
            half_width = max(left_space, right_space)
            preview_width = vs_pix.width() + 2 * half_width
            preview_height = max(p.height() for p in preview_parts)
            preview_pix = QtGui.QPixmap(preview_width, preview_height)
            preview_pix.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(preview_pix)
            vs_x = (preview_width - vs_pix.width()) // 2
            vs_y = (preview_height - vs_pix.height()) // 2
            p1_x = vs_x - p1.width() - padding
            p1_y = (preview_height - p1.height()) // 2
            p2_x = vs_x + vs_pix.width() + padding + extra_after_vs - p2.width()
            p2_y = (preview_height - p2.height()) // 2
            painter.drawPixmap(p1_x, p1_y, p1)
            painter.drawPixmap(vs_x, vs_y, vs_pix)
            painter.drawPixmap(p2_x, p2_y, p2)
            painter.end()
        else:
            preview_width = sum(p.width() for p in preview_parts)
            preview_height = max(p.height() for p in preview_parts)
            preview_pix = QtGui.QPixmap(preview_width, preview_height)
            preview_pix.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(preview_pix)
            x = 0
            for p in preview_parts:
                painter.drawPixmap(x, (preview_height - p.height()) // 2, p)
                x += p.width()
            painter.end()

        legend_height = 400
        preview_with_key = QtGui.QPixmap(
            preview_pix.width(), preview_pix.height() + legend_height
        )
        preview_with_key.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(preview_with_key)
        painter.drawPixmap(0, 0, preview_pix)
        painter.setPen(QtGui.QColor("white"))
        small_font = QtGui.QFont("Times New Roman", 160)
        painter.setFont(small_font)
        fm = painter.fontMetrics()
        margin = 100
        names = [
            self.army1_frame.name_edit.text() or "Army 1",
            self.army2_frame.name_edit.text() or "Army 2",
        ]
        for i, name in enumerate(names):
            text_y = preview_pix.height() + fm.ascent() + margin
            text_x = (
                margin
                if i == 0
                else preview_pix.width() - fm.horizontalAdvance(name) - margin
            )
            painter.drawText(text_x, text_y, name)
        painter.end()
        preview_pix = preview_with_key

        return preview_pix, hist_pixmaps

    def render_preview_pixmap(self) -> QtGui.QPixmap | None:
        """Render just the army preview section."""
        preview, _ = self._generate_preview_and_hist_pixmaps()
        return preview

    def get_histogram_pixmaps(self) -> dict[str, QtGui.QPixmap]:
        """Return histogram pixmaps keyed by identifier."""
        _, hist = self._generate_preview_and_hist_pixmaps()
        return hist

    def get_pdf_item_pixmap(self, item_type: str) -> QtGui.QPixmap | None:
        """Return pixmap for the given PDF layout item ``item_type``."""
        if item_type == "preview":
            return self.render_preview_pixmap()
        if item_type == "army_composition":
            return self._render_army_composition_pixmap()
        return self.get_histogram_pixmaps().get(item_type)

    def render_summary_pixmap(self, with_background: bool = True) -> QtGui.QPixmap | None:
        """Render the summary image and return it as a pixmap."""

        preview_pix, hist_pixmaps = self._generate_preview_and_hist_pixmaps()
        if preview_pix is None or not hist_pixmaps:
            return None

        final_width = max(preview_pix.width(), *(p.width() for p in hist_pixmaps.values()))
        final_height = preview_pix.height() + sum(p.height() for p in hist_pixmaps.values())
        final_pix = QtGui.QPixmap(final_width, final_height)
        if with_background:
            painter = QtGui.QPainter(final_pix)
            gradient = QtGui.QLinearGradient(0, 0, 0, final_height)
            gradient.setColorAt(0, QtGui.QColor("#4a4a4a"))
            gradient.setColorAt(1, QtGui.QColor("#1e1e1e"))
            painter.fillRect(final_pix.rect(), gradient)
        else:
            final_pix.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(final_pix)
        x = (final_width - preview_pix.width()) // 2
        painter.drawPixmap(x, 0, preview_pix)
        y = preview_pix.height()
        for p in hist_pixmaps.values():
            x = (final_width - p.width()) // 2
            painter.drawPixmap(x, y, p)
            y += p.height()

        if with_background:
            painter.setPen(QtGui.QColor("white"))
            weight_obj = getattr(QtGui.QFont, "Weight", None)
            bold_weight = getattr(weight_obj, "Bold", None) if weight_obj is not None else None
            if bold_weight is None:
                bold_weight = getattr(QtGui.QFont, "Bold")
            title_font = QtGui.QFont("Times New Roman", 240, bold_weight)
            painter.setFont(title_font)
            margin = 40
            title_text = "Matchup Statistics"
            fm = painter.fontMetrics()
            title_width = fm.horizontalAdvance(title_text)
            painter.save()
            painter.translate(margin + fm.ascent(), (final_height + title_width) // 2)
            painter.rotate(-90)
            painter.drawText(0, 0, title_text)
            painter.restore()
            small_font = QtGui.QFont("Times New Roman", 160)
            painter.setFont(small_font)
            label = "OMNI"
            fm = painter.fontMetrics()
            x = final_width - fm.horizontalAdvance(label) - margin
            y = final_height - fm.descent() - margin
            painter.drawText(x, y, label)
        painter.end()
        return final_pix

    def _render_army_composition_pixmap(self) -> QtGui.QPixmap:
        cfgs = [self.army1_frame.build_config(), self.army2_frame.build_config()]
        lines: list[str] = []
        for idx, cfg in enumerate(cfgs, start=1):
            lines.append(f"Army {idx}: {cfg['army_name']}")
            lines.append(
                f"  Unit: {cfg['unit_type']} T{cfg['tier']}  Count: {cfg['count']:,}")
            lines.append(
                f"  Atk/Def/HP mods: {cfg['atk_mod']:+.1f}/{cfg['def_mod']:+.1f}/{cfg['hp_mod']:+.1f}")
            heroes = ", ".join(h.get("hero_name_or_preset", "") for h in cfg["heroes"]) or "None"
            lines.append(f"  Heroes: {heroes}")
            lines.append("")
        font = QtGui.QFont("Times New Roman", 160)
        fm = QtGui.QFontMetrics(font)
        width = max(fm.horizontalAdvance(line) for line in lines)
        height = fm.height() * len(lines)
        margin = 80
        pix = QtGui.QPixmap(width + margin * 2, height + margin * 2)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pix)
        painter.setPen(QtGui.QColor("white"))
        painter.setFont(font)
        y = margin + fm.ascent()
        for line in lines:
            painter.drawText(margin, y, line)
            y += fm.height()
        painter.end()
        return pix

    def export_summary_image(self) -> None:
        """Combine preview and histogram images into a single PNG."""
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
                if pm.isNull():
                    continue
                pm = make_transparent(pm)
                hist_pixmaps.append(pm)
        if not hist_pixmaps:
            QtWidgets.QMessageBox.warning(
                self, "No Figures", "No histogram images found. Run a simulation first."
            )
            return

        # Capture army previews and vs image
        scale = 5

        def render_preview(widget: QtWidgets.QWidget) -> QtGui.QPixmap:
            pix = QtGui.QPixmap(widget.size())
            pix.fill(QtCore.Qt.GlobalColor.transparent)
            flags = QtWidgets.QWidget.RenderFlag.DrawChildren
            widget.render(pix, QtCore.QPoint(), QtGui.QRegion(), flags)
            return pix.scaled(
                widget.width() * scale,
                widget.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )

        p1 = render_preview(self.army1_frame.preview_widget)
        p2 = render_preview(self.army2_frame.preview_widget)
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
            extra_after_vs = 1700

            # Calculate width so the VS icon sits exactly in the middle of the
            # preview image. This may introduce extra blank space on the shorter
            # side, but ensures the icon is horizontally centered in the final
            # summary.
            left_space = p1.width() + padding
            right_space = p2.width() + padding + extra_after_vs
            half_width = max(left_space, right_space)
            preview_width = vs_pix.width() + 2 * half_width
            preview_height = max(p.height() for p in preview_parts)

            # Account for the width of the right army so a margin is preserved
            # when shifting it left or right via ``extra_after_vs``.  Calculate a
            # preliminary VS position using the half-width, then expand the
            # preview canvas if needed to keep a padding margin on the right.
            vs_x = half_width
            right_x = vs_x + vs_pix.width() + padding + extra_after_vs - p2.width()
            preview_width = max(preview_width, right_x + p2.width() + padding)

            preview_pix = QtGui.QPixmap(preview_width, preview_height)
            preview_pix.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(preview_pix)

            # Position the VS icon in the horizontal centre using the final
            # width of the preview image
            vs_x = (preview_width - vs_pix.width()) // 2
            vs_y = (preview_height - vs_pix.height()) // 2
            painter.drawPixmap(vs_x, vs_y, vs_pix)

            # Draw the army previews relative to the centred VS icon
            left_x = vs_x - padding - p1.width()
            y = (preview_height - p1.height()) // 2
            painter.drawPixmap(left_x, y, p1)

            right_x = vs_x + vs_pix.width() + padding + extra_after_vs - p2.width()
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

        # Add a legend below the army previews so exported summaries clearly
        # indicate which side belongs to which army.  Each entry shows a coloured
        # square (red for the first army and green for the second) alongside the
        # army's name.
        legend_height = 200
        preview_with_key = QtGui.QPixmap(preview_pix.width(), preview_pix.height() + legend_height)
        preview_with_key.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(preview_with_key)
        painter.drawPixmap(0, 0, preview_pix)
        painter.setPen(QtGui.QColor("white"))

        weight_obj = getattr(QtGui.QFont, "Weight", None)
        bold_weight = getattr(weight_obj, "Bold", None) if weight_obj is not None else None
        if bold_weight is None:
            bold_weight = getattr(QtGui.QFont, "Bold")
        legend_font = QtGui.QFont("Times New Roman", 80, bold_weight)
        painter.setFont(legend_font)
        fm = painter.fontMetrics()

        army_names = [
            self.army1_frame.name_edit.text() or "Army 1",
            self.army2_frame.name_edit.text() or "Army 2",
        ]
        colors = [QtGui.QColor("green"), QtGui.QColor("red")]
        square_size = 100
        spacing = 40
        y = preview_pix.height() + (legend_height - square_size) // 2
        for idx, (name, color) in enumerate(zip(army_names, colors)):
            center_x = preview_pix.width() * (1 / 4 if idx == 0 else 3 / 4)
            text_width = fm.horizontalAdvance(name)
            total_width = square_size + spacing + text_width
            x = int(center_x - total_width / 2)
            painter.fillRect(x, y, square_size, square_size, color)
            painter.drawRect(x, y, square_size, square_size)
            text_x = x + square_size + spacing
            text_y = int(y + square_size / 2 + (fm.ascent() - fm.descent()) / 2)
            painter.drawText(text_x, text_y, name)

        painter.end()
        preview_pix = preview_with_key

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

        painter.setPen(QtGui.QColor("white"))

        # Use a serif font to match the game's styling. The "Matchup Statistics"
        # title is larger than the label in the bottom corner.
        weight_obj = getattr(QtGui.QFont, "Weight", None)
        bold_weight = getattr(weight_obj, "Bold", None) if weight_obj is not None else None
        if bold_weight is None:
            bold_weight = getattr(QtGui.QFont, "Bold")
        title_font = QtGui.QFont("Times New Roman", 240, bold_weight)
        painter.setFont(title_font)

        margin = 40
        title_text = "Matchup Statistics"
        fm = painter.fontMetrics()
        title_width = fm.horizontalAdvance(title_text)
        painter.save()
        painter.translate(margin + fm.ascent(), (final_height + title_width) // 2)
        painter.rotate(-90)
        painter.drawText(0, 0, title_text)
        painter.restore()

        label_font = QtGui.QFont("Times New Roman", 80, bold_weight)
        painter.setFont(label_font)
        fm = painter.fontMetrics()
        label = "OMNI"
        x = final_width - fm.horizontalAdvance(label) - margin
        y = final_height - fm.descent() - margin
        painter.drawText(x, y, label)
        painter.end()

        army_names_preview = [
            self.army1_frame.name_edit.text() or "Army 1",
            self.army2_frame.name_edit.text() or "Army 2",
        ]
        base_name = _default_export_basename(
            army_names_preview[0],
            army_names_preview[1] if len(army_names_preview) > 1 else "Army 2",
        )
        initial_path = os.path.join(self.last_setup_dir, f"{base_name}.png")
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Summary Image",
            initial_path,
            "PNG Files (*.png)"
        )
        if save_path:
            final_pix.save(save_path, "PNG")
            self.last_setup_dir = os.path.dirname(save_path)

    def _export_summary_html(
        self,
        *,
        include_sample_details: bool,
        include_sample_log: bool = True,
        dialog_title: str,
        filename_suffix: str,
    ) -> None:
        """Export the latest battle summary as an interactive HTML bundle."""

        payload = self._last_simulation_payload
        if not payload:
            QtWidgets.QMessageBox.warning(
                self,
                "No Summary Data",
                "Run a simulation to generate data for the HTML export.",
            )
            return

        timestamp = payload.get("generated_at") or time.time()
        setup = payload.get("setup") or []
        army_names = payload.get("army_names") or [
            cfg.get("army_name", f"Army {i + 1}") for i, cfg in enumerate(setup)
        ]
        army_one_name = army_names[0] if army_names else "Army 1"
        army_two_name = army_names[1] if len(army_names) > 1 else "Army 2"
        base_name = _default_export_basename(army_one_name, army_two_name, timestamp)
        default_name = f"{base_name}_{filename_suffix}.html"
        initial_path = os.path.join(self.last_setup_dir, default_name)
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            dialog_title,
            initial_path,
            "HTML Files (*.html)",
        )
        if not save_path:
            return

        if not save_path.lower().endswith(".html"):
            save_path += ".html"

        copied_assets: dict[tuple[str, tuple | None, tuple | None], str] = {}

        hist_color = HISTOGRAM_BG_COLOR.lstrip("#")
        if len(hist_color) != 6:
            hist_color = hist_color[:6].ljust(6, "0")
        histogram_bg_tuple = tuple(int(hist_color[i : i + 2], 16) for i in range(0, 6, 2))

        def _transparent_histogram_bytes(path: str) -> bytes:
            with Image.open(path) as img:
                converted = img.convert("RGBA")
                data = np.array(converted, dtype=np.uint8)
                if data.size == 0:
                    buf = io.BytesIO()
                    converted.save(buf, format="PNG")
                    return buf.getvalue()
                bg = np.array(histogram_bg_tuple, dtype=np.int16)
                rgb = data[..., :3].astype(np.int16)
                diff = np.abs(rgb - bg)
                mask = (diff <= 2).all(axis=-1)
                data[..., 3][mask] = 0
                result = Image.fromarray(data.astype(np.uint8), mode="RGBA")
                buf = io.BytesIO()
                result.save(buf, format="PNG")
                return buf.getvalue()

        def _parse_argb_hex(value: str) -> tuple[int, int, int, int] | None:
            val = value.strip()
            if val.startswith("#"):
                val = val[1:]
            try:
                if len(val) == 8:
                    a = int(val[0:2], 16)
                    r = int(val[2:4], 16)
                    g = int(val[4:6], 16)
                    b = int(val[6:8], 16)
                    return (r, g, b, a)
                if len(val) == 6:
                    r = int(val[0:2], 16)
                    g = int(val[2:4], 16)
                    b = int(val[4:6], 16)
                    return (r, g, b, 255)
            except ValueError:
                return None
            return None

        def _render_star_overlay(src: str, overlay: dict[str, Any]) -> bytes:
            base = Image.open(src).convert("RGBA")
            width, height = base.size
            max_stars = max(1, int(overlay.get("max", 6)))
            count = max(0, min(max_stars, int(overlay.get("count", max_stars))))
            if count >= max_stars:
                buf = io.BytesIO()
                base.save(buf, format="PNG")
                return buf.getvalue()
            vertical_ratio = float(overlay.get("vertical_ratio", 0.8))
            side_margin = float(overlay.get("side_margin", 0.0))
            star_width = width * (1 - 2 * side_margin) / max_stars if max_stars else width
            star_height = height * (1 - vertical_ratio)
            if star_width <= 0 or star_height <= 0:
                buf = io.BytesIO()
                base.save(buf, format="PNG")
                return buf.getvalue()
            x_offset = width * side_margin
            y_base = height - star_height
            overlay_img = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay_img)
            v_offsets = overlay.get("v_offsets") or []
            h_offsets = overlay.get("h_offsets") or []
            color_raw = overlay.get("color") or (100, 100, 100, 180)
            if isinstance(color_raw, (list, tuple)):
                color_vals = list(color_raw)
            else:
                color_vals = [100, 100, 100, 180]
            if len(color_vals) == 3:
                color_vals.append(255)
            while len(color_vals) < 4:
                color_vals.append(255)
            color_rgba = tuple(
                int(max(0, min(255, round(val)))) for val in color_vals[:4]
            )
            for idx in range(count, max_stars):
                v_off = v_offsets[idx] * star_height if idx < len(v_offsets) else 0.0
                h_off = h_offsets[idx] * star_width if idx < len(h_offsets) else 0.0
                cx = x_offset + idx * star_width + h_off + star_width / 2
                cy = y_base + v_off + star_height / 2
                outer_r = min(star_width, star_height) / 2
                inner_r = outer_r * 0.4
                points = []
                for i in range(8):
                    angle = math.radians(-90 + i * 45)
                    radius = outer_r if i % 2 == 0 else inner_r
                    points.append(
                        (
                            cx + radius * math.cos(angle),
                            cy + radius * math.sin(angle),
                        )
                    )
                draw.polygon(points, fill=color_rgba)
            combined = Image.alpha_composite(base, overlay_img)
            buf = io.BytesIO()
            combined.save(buf, format="PNG")
            return buf.getvalue()

        def ensure_asset(
            src: str | None,
            dest_rel: str | None = None,
            *,
            star_overlay: dict[str, Any] | None = None,
        ) -> str | None:
            del dest_rel  # compatibility placeholder
            if not src or not os.path.exists(src):
                return None
            overlay_key: tuple | None = None
            histogram_variant: tuple | None = None
            make_transparent_histogram = False
            if star_overlay:
                try:
                    count_val = int(star_overlay.get("count", 0))
                    max_val = max(1, int(star_overlay.get("max", 0)))
                except Exception:
                    count_val = 0
                    max_val = 0
                if count_val >= max_val or max_val <= 0:
                    star_overlay = None
                else:
                    color_vals = star_overlay.get("color", (100, 100, 100, 180))
                    if not isinstance(color_vals, (list, tuple)):
                        color_vals = (100, 100, 100, 180)
                    if len(color_vals) == 3:
                        color_vals = (*color_vals, 255)
                    overlay_key = (
                        count_val,
                        max_val,
                        float(star_overlay.get("vertical_ratio", 0.0)),
                        float(star_overlay.get("side_margin", 0.0)),
                        tuple(float(x) for x in star_overlay.get("v_offsets", ())),
                        tuple(float(x) for x in star_overlay.get("h_offsets", ())),
                        tuple(int(max(0, min(255, round(v)))) for v in color_vals[:4]),
                    )
            elif os.path.splitext(src)[1].lower() == ".png":
                base_name = os.path.basename(src).lower()
                if base_name in {"own_remaining_troops.png", "enemy_remaining_troops.png"}:
                    make_transparent_histogram = True
                    histogram_variant = ("transparent-bg",)

            key = (os.path.abspath(src), overlay_key, histogram_variant)
            cached = copied_assets.get(key)
            if cached:
                return cached
            try:
                if star_overlay:
                    raw = _render_star_overlay(src, star_overlay)
                    mime_type = "image/png"
                elif make_transparent_histogram:
                    raw = _transparent_histogram_bytes(src)
                    mime_type = "image/png"
                else:
                    with open(src, "rb") as fh:
                        raw = fh.read()
                    mime_type = mimetypes.guess_type(src)[0] or "application/octet-stream"
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load asset {os.path.basename(src)}: {exc}",
                )
                return None
            except Exception:
                try:
                    with open(src, "rb") as fh:
                        raw = fh.read()
                except OSError as exc:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to load asset {os.path.basename(src)}: {exc}",
                    )
                    return None
                mime_type = mimetypes.guess_type(src)[0] or "application/octet-stream"
            data_uri = "data:" + mime_type + ";base64," + base64.b64encode(raw).decode("ascii")
            copied_assets[key] = data_uri
            return data_uri

        def build_star_overlay_info(
            image_path: str | None,
            *,
            is_plugin: bool,
            star_count: int | None,
        ) -> dict[str, Any] | None:
            if not image_path or star_count is None:
                return None
            try:
                count_val = int(star_count)
            except (TypeError, ValueError):
                return None
            defaults = {
                "max": 6,
                "vertical_ratio": (
                    StarredImageLabel.PLUGIN_STAR_VERTICAL_RATIO
                    if is_plugin
                    else StarredImageLabel.HERO_STAR_VERTICAL_RATIO
                ),
                "side_margin": (
                    StarredImageLabel.PLUGIN_STAR_SIDE_MARGIN_RATIO
                    if is_plugin
                    else StarredImageLabel.HERO_STAR_SIDE_MARGIN_RATIO
                ),
                "v_offsets": list(
                    StarredImageLabel.PLUGIN_STAR_V_OFFSETS
                    if is_plugin
                    else StarredImageLabel.HERO_STAR_V_OFFSETS
                ),
                "h_offsets": list(
                    StarredImageLabel.PLUGIN_STAR_H_OFFSETS
                    if is_plugin
                    else StarredImageLabel.HERO_STAR_H_OFFSETS
                ),
                "color": (100, 100, 100, 180),
            }
            meta_path = os.path.splitext(image_path)[0] + ".json"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as fh:
                        meta = json.load(fh)
                    defaults["max"] = int(meta.get("max_stars", defaults["max"]))
                    defaults["vertical_ratio"] = float(
                        meta.get("star_vertical_ratio", defaults["vertical_ratio"])
                    )
                    defaults["side_margin"] = float(
                        meta.get("star_side_margin_ratio", defaults["side_margin"])
                    )
                    if isinstance(meta.get("v_offsets"), (list, tuple)):
                        defaults["v_offsets"] = [float(x) for x in meta["v_offsets"]]
                    if isinstance(meta.get("h_offsets"), (list, tuple)):
                        defaults["h_offsets"] = [float(x) for x in meta["h_offsets"]]
                    color_value = meta.get("star_color")
                    if color_value:
                        parsed = _parse_argb_hex(str(color_value))
                        if parsed:
                            defaults["color"] = parsed
                except Exception:
                    pass
            max_stars = max(1, int(defaults["max"]))
            count_val = max(0, min(max_stars, int(count_val)))
            if count_val >= max_stars:
                return None
            return {
                "count": count_val,
                "max": max_stars,
                "vertical_ratio": defaults["vertical_ratio"],
                "side_margin": defaults["side_margin"],
                "v_offsets": defaults["v_offsets"],
                "h_offsets": defaults["h_offsets"],
                "color": defaults["color"],
            }

        base_dir = os.path.dirname(__file__)

        def normalize_key(value: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (value or "").lower())

        def build_lookup(directory: str) -> dict[str, str]:
            lookup: dict[str, str] = {}
            if not os.path.isdir(directory):
                return lookup
            for fname in os.listdir(directory):
                if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                key = normalize_key(os.path.splitext(fname)[0])
                if key:
                    lookup[key] = os.path.join(directory, fname)
            return lookup

        def resolve_from_lookup(label: str, lookup: dict[str, str]) -> str | None:
            if not label:
                return None
            key = normalize_key(label)
            path = lookup.get(key)
            if not path and key:
                matches = difflib.get_close_matches(key, list(lookup.keys()), n=1, cutoff=0.75)
                if matches:
                    path = lookup.get(matches[0])
            return path

        icon_lookup = build_lookup(os.path.join(base_dir, "Icons"))
        plugin_icon_lookup = build_lookup(os.path.join(base_dir, "Plugin Skill Images"))
        mount_icon_lookup = build_lookup(os.path.join(base_dir, "MountSkillsIcons"))

        stat_icons = {
            "attack": ensure_asset(os.path.join(base_dir, "Stat Icons", "attack.png")),
            "defense": ensure_asset(os.path.join(base_dir, "Stat Icons", "defense.png")),
            "health": ensure_asset(os.path.join(base_dir, "Stat Icons", "health.png")),
        }
        bonus_icon = ensure_asset(
            os.path.join(base_dir, "Stat Icons", "Additional_stats_Icon.png"),
            "icons/bonus_stats.png",
        )
        gear_background_lookup: dict[str, str | None] = {}
        for rarity, bg_path in RARITY_BACKGROUNDS.items():
            if bg_path and os.path.exists(bg_path):
                gear_background_lookup[rarity] = ensure_asset(bg_path)
        mount_placeholder = ensure_asset(
            os.path.join(base_dir, "MountSkillsIcons", "none.png"),
            "mounts/placeholder.png",
        )

        jewel_icon_map: dict[str, str] = {}
        for slot_key, slot_label in JEWEL_SLOTS:
            icon_path = resolve_from_lookup(slot_label, icon_lookup)
            jewel_icon_map[slot_key] = ensure_asset(icon_path) if icon_path else None

        histogram_lookup: dict[str, str | None] = {}
        for hist_path in payload.get("histograms") or []:
            if not hist_path:
                continue
            filename = os.path.basename(hist_path)
            if not filename:
                continue
            histogram_lookup[filename.lower()] = ensure_asset(hist_path)

        summary_data = payload.get("summary") or []
        win_rate = float(payload.get("win_rate", 0.0) or 0.0)
        runs = max(int(payload.get("runs", 0)), 0)
        army_one_pct = max(0.0, min(100.0, win_rate * 100.0 if runs else 0.0))
        army_two_pct = max(0.0, 100.0 - army_one_pct)
        army_one_wins = int(round((army_one_pct / 100.0) * runs)) if runs else 0
        army_two_wins = runs - army_one_wins

        best_match_data = payload.get("best_match")
        if not isinstance(best_match_data, dict):
            best_match_data = None

        sample_data_raw: dict[str, Any] = {}
        if include_sample_details:
            raw_sample = payload.get("sample_battle")
            if isinstance(raw_sample, dict):
                sample_data_raw = raw_sample
        round_details = payload.get("rounds") if include_sample_details else None
        if not isinstance(round_details, list):
            round_details = []

        sample_histories: list[dict[str, Any]] = []
        if include_sample_details and sample_data_raw:
            raw_histories = sample_data_raw.get("army_histories")
            if isinstance(raw_histories, list):
                for idx, history in enumerate(raw_histories):
                    if not isinstance(history, dict):
                        continue
                    raw_troops = history.get("troops")
                    raw_unrevivable = history.get("unrevivable")
                    troops: list[int] = []
                    if isinstance(raw_troops, list):
                        for value in raw_troops:
                            try:
                                troops.append(int(round(float(value))))
                            except (TypeError, ValueError):
                                troops.append(0)
                    unrevivable: list[int] = []
                    if isinstance(raw_unrevivable, list):
                        for value in raw_unrevivable:
                            try:
                                unrevivable.append(int(round(float(value))))
                            except (TypeError, ValueError):
                                unrevivable.append(0)
                    label = history.get("name")
                    if not isinstance(label, str) or not label.strip():
                        label = (
                            army_names[idx]
                            if idx < len(army_names)
                            else f"Army {idx + 1}"
                        )
                    sample_histories.append(
                        {
                            "name": label,
                            "troops": troops,
                            "unrevivable": unrevivable,
                        }
                    )

        def fmt_percent(value: float, invert: bool = False) -> str:
            percent = -value * 100 if invert else value * 100
            return f"{percent:+.1f}%"

        def fmt_int(value: Any) -> str:
            try:
                return f"{int(round(float(value))):,}"
            except (TypeError, ValueError):
                return "0"

        def coerce_numeric(value: Any) -> float | None:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.replace(",", "").strip()
                if not stripped:
                    return None
                try:
                    return float(stripped)
                except ValueError:
                    return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def normalize_metadata_text(value: Any) -> str:
            """Coerce summary metadata into a clean string for HTML rendering."""

            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, (bytes, bytearray)):
                try:
                    return value.decode("utf-8")
                except Exception:
                    return value.decode("utf-8", errors="ignore")
            if isinstance(value, (list, tuple, set)):
                parts = [normalize_metadata_text(part).strip() for part in value]
                parts = [part for part in parts if part]
                return ", ".join(parts)
            if isinstance(value, dict):
                segments: list[str] = []
                for key, sub_value in value.items():
                    key_text = normalize_metadata_text(key).strip()
                    value_text = normalize_metadata_text(sub_value).strip()
                    if key_text and value_text:
                        segments.append(f"{key_text}: {value_text}")
                    elif value_text:
                        segments.append(value_text)
                    elif key_text:
                        segments.append(key_text)
                return ", ".join(segment for segment in segments if segment)
            try:
                return str(value)
            except Exception:
                return ""

        def build_skill_display(skill_id: str) -> tuple[str, str, dict[str, Any] | None]:
            if not skill_id:
                return "Unknown Skill", "Description unavailable.", None
            skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id)
            fallback_name = skill_id.replace("_", " ").title()
            if isinstance(skill_def, dict):
                name = normalize_metadata_text(skill_def.get("name")) or fallback_name
            else:
                name = fallback_name
            description_raw = get_skill_description(skill_id, name) if skill_id else None
            description = normalize_metadata_text(description_raw)
            tooltip = (
                html.escape(description).replace("\n", "<br>")
                if description
                else "Description unavailable."
            )
            return name, tooltip, skill_def if isinstance(skill_def, dict) else None

        def resolve_skill_icon(skill_id: str, skill_name: str | None) -> str | None:
            preferred_label = skill_name or skill_id
            skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id) or {}
            if _is_mount_skill(skill_id):
                path = resolve_from_lookup(preferred_label, mount_icon_lookup) or resolve_from_lookup(
                    skill_def.get("name", skill_id), mount_icon_lookup
                )
                if path:
                    return ensure_asset(path)
            path = resolve_from_lookup(preferred_label, plugin_icon_lookup) or resolve_from_lookup(
                skill_def.get("name", skill_id), plugin_icon_lookup
            )
            if path:
                return ensure_asset(path)
            return None

        armies_html: list[str] = []
        sample_army_blocks: list[str] = []
        skill_columns: list[dict[str, Any]] = [
            {"key": "casts", "label": "Casts", "is_boosted": False, "icon": None},
            {"key": "kills", "label": "Kills", "is_boosted": False, "icon": None},
            {"key": "heals", "label": "Heals", "is_boosted": False, "icon": None},
            {"key": "shielded", "label": "Shielded", "is_boosted": False, "icon": None},
            {
                "key": "damage_reduced",
                "label": "Damage Reduced",
                "is_boosted": False,
                "icon": None,
            },
            {"key": "rage", "label": "Rage", "is_boosted": False, "icon": None},
            {
                "key": "rage_reduced",
                "label": "Rage Reduced",
                "is_boosted": False,
                "icon": None,
            },
            {
                "key": "boosted_kills",
                "label": "Boosted Kills",
                "is_boosted": True,
                "icon": None,
            },
            {
                "key": "boosted_heals",
                "label": "Boosted Heals",
                "is_boosted": True,
                "icon": None,
            },
            {
                "key": "boosted_shielded",
                "label": "Boosted Shielded",
                "is_boosted": True,
                "icon": None,
            },
            {
                "key": "boosted_rage",
                "label": "Boosted Rage",
                "is_boosted": True,
                "icon": None,
            },
            {
                "key": "boosted_rage_reduced",
                "label": "Boosted Rage Reduced",
                "is_boosted": True,
                "icon": None,
            },
            {
                "key": "boosted_damage_reduced",
                "label": "Boosted Damage Reduced",
                "is_boosted": True,
                "icon": None,
            },
        ]
        for idx, summary_entry in enumerate(summary_data):
            cfg = setup[idx] if idx < len(setup) else {}
            army_name = cfg.get("army_name") or (
                army_names[idx] if idx < len(army_names) else f"Army {idx + 1}"
            )
            unit_type = cfg.get("unit_type", "pikemen")
            unit_icon_path = resolve_from_lookup(unit_type, icon_lookup)
            unit_icon = ensure_asset(unit_icon_path) if unit_icon_path else None
            tier = cfg.get("tier", 0)
            troop_count = cfg.get("count", 0)
            atk_mod = float(cfg.get("atk_mod", 0.0))
            def_mod = float(cfg.get("def_mod", 0.0))
            hp_mod = float(cfg.get("hp_mod", 0.0))
            bonus_stats = merge_bonus_stats(default_bonus_stats(), cfg.get("bonus_stats"))
            bonus_entries = [
                {
                    "label": entry["label"],
                    "value": fmt_percent(entry["value"], entry["invert"]),
                }
                for entry in iter_bonus_stat_entries(bonus_stats)
            ]
            for entry in summary_entry.get("passive_bonus_entries", []) or []:
                try:
                    label = entry.get("label")
                    value = fmt_percent(
                        float(entry.get("value", 0.0)),
                        bool(entry.get("invert", False)),
                    )
                except (TypeError, ValueError):
                    continue
                if label:
                    bonus_entries.append({"label": str(label), "value": value})
            stats_html = []
            for key, label in (("attack", "Attack"), ("defense", "Defense"), ("health", "Health")):
                icon = stat_icons.get(key) or ""
                value = {"attack": atk_mod, "defense": def_mod, "health": hp_mod}[key]
                stats_html.append(
                    "<div class=\"stat-chip\">"
                    + (f"<img src=\"{icon}\" alt=\"{label} icon\">" if icon else "")
                    + f"<span>{label}</span><strong>{fmt_percent(value)}</strong></div>"
                )

            gem_skills = cfg.get("gem_skills", {}) or {}
            hero_skill_lists = summary_entry.get("skills") or []
            jewel_cards: list[str] = []
            for slot_key, slot_label in JEWEL_SLOTS:
                raw_skill = gem_skills.get(slot_key, "")
                skill_id = normalize_gem_skill_id(raw_skill)
                entry = None
                hero_index = JEWEL_SLOT_HERO_INDEX.get(slot_key, 0)
                if hero_index >= 0 and hero_index < len(hero_skill_lists):
                    entry = next(
                        (
                            e
                            for e in hero_skill_lists[hero_index]
                            if isinstance(e, dict) and e.get("id") == skill_id
                        ),
                        None,
                    )
                skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id) if skill_id else None
                skill_name = None
                if isinstance(entry, dict):
                    skill_name = normalize_metadata_text(entry.get("name")) or None
                if not skill_name and isinstance(skill_def, dict):
                    skill_name = normalize_metadata_text(skill_def.get("name")) or None
                if not skill_name and skill_id:
                    skill_name = normalize_metadata_text(skill_id)
                rarity_raw = entry.get("rarity") if isinstance(entry, dict) else None
                rarity = normalize_metadata_text(rarity_raw)
                desc_raw = get_skill_description(skill_id, skill_name) if skill_id else None
                desc = normalize_metadata_text(desc_raw)
                tooltip_base = (
                    html.escape(desc).replace("\n", "<br>")
                    if desc
                    else "Skill details coming soon."
                )
                if rarity:
                    tooltip = f"{tooltip_base}<br><em>Rarity: {html.escape(rarity)}</em>"
                else:
                    tooltip = tooltip_base
                display_name_raw = skill_name or "None"
                if rarity and rarity not in display_name_raw:
                    display_name_raw = f"{display_name_raw} ({rarity})"
                display_name_text = normalize_metadata_text(display_name_raw)
                display_name = html.escape(display_name_text) if display_name_text else "None"
                slot_display = html.escape(slot_label)
                jewel_icon = jewel_icon_map.get(slot_key) or ""
                jewel_cards.append(
                    "<div class=\"jewel-card\">"
                    + (f"<img src=\"{jewel_icon}\" alt=\"{slot_display} icon\">" if jewel_icon else "")
                    + "<div class=\"jewel-text\">"
                    + f"<span class=\"jewel-slot\">{slot_display}</span>"
                    + f"<span class=\"jewel-skill tooltip\" tabindex=\"0\">{display_name}<span class=\"tooltip-content\"><strong>{display_name}</strong><p>{tooltip}</p></span></span>"
                    + "</div></div>"
                )

            if not jewel_cards:
                jewel_cards.append("<p class=\"empty-state\">No jewels assigned.</p>")

            hero_names = summary_entry.get("hero_names") or []
            heroes_cfg = cfg.get("heroes", []) or []
            portrait_paths = [
                summary_entry.get("portrait1"),
                summary_entry.get("portrait2"),
            ]
            hero_cards: list[str] = []
            gear_bonus_entries: list[dict[str, str]] = []
            hero_count = max(len(hero_names), len(heroes_cfg))
            for hero_idx in range(hero_count):
                hero_cfg = heroes_cfg[hero_idx] if hero_idx < len(heroes_cfg) else {}
                portrait_path = (
                    portrait_paths[hero_idx]
                    if hero_idx < len(portrait_paths)
                    else None
                )
                cfg_name = hero_cfg.get("hero_name_or_preset", "")
                raw_name = (
                    cfg_name
                    or (hero_names[hero_idx] if hero_idx < len(hero_names) else "")
                    or f"Hero {hero_idx + 1}"
                )
                name_display = html.escape(raw_name)
                is_primary_flag = False
                if isinstance(hero_cfg, dict):
                    for primary_key in (
                        "is_primary_hero",
                        "is_primary",
                        "primary",
                        "primary_hero",
                    ):
                        if primary_key in hero_cfg:
                            is_primary_flag = bool(hero_cfg.get(primary_key))
                            break
                if not is_primary_flag:
                    primary_idx = summary_entry.get("primary_hero_index")
                    if isinstance(primary_idx, int):
                        is_primary_flag = primary_idx == hero_idx
                    else:
                        primary_indices = summary_entry.get("primary_hero_indices")
                        if isinstance(primary_indices, (list, tuple, set)):
                            try:
                                is_primary_flag = hero_idx in primary_indices
                            except TypeError:
                                is_primary_flag = False
                is_primary_hero = is_primary_flag or hero_idx == 0
                hero_name_markup = f'<span class="hero-name">{name_display}</span>'
                badge_markup = (
                    '<span class="hero-badge">Main Hero</span>' if is_primary_hero else ""
                )
                header_markup = f"<div><h4>{hero_name_markup}{badge_markup}</h4></div>"
                star_value = hero_cfg.get("star_count") if isinstance(hero_cfg, dict) else None
                portrait_overlay = build_star_overlay_info(
                    portrait_path,
                    is_plugin=False,
                    star_count=star_value,
                )
                portrait_uri = (
                    ensure_asset(portrait_path, star_overlay=portrait_overlay)
                    if portrait_path
                    else None
                )
                portrait_html = (
                    f"<img src=\"{portrait_uri}\" alt=\"{name_display} portrait\" class=\"hero-portrait\">"
                    if portrait_uri
                    else ""
                )

                talent_ids = hero_cfg.get("talent_ids", []) or []
                base_skill_ids = hero_cfg.get("base_skill_ids", []) or []
                plugin_skill_ids = hero_cfg.get("plugin_skill_ids", []) or []
                plugin_star_counts = (
                    list(hero_cfg.get("plugin_star_counts", []))
                    if isinstance(hero_cfg, dict)
                    else []
                )

                talent_chips: list[str] = []
                for tid in talent_ids:
                    t_name, tooltip, _ = build_skill_display(tid)
                    safe_name = html.escape(t_name)
                    talent_chips.append(
                        "<span class=\"skill-pill tooltip\" tabindex=\"0\">"
                        + safe_name
                        + f"<span class=\"tooltip-content\"><strong>{safe_name}</strong><p>{tooltip}</p></span>"
                        + "</span>"
                    )

                skill_chips: list[str] = []
                for sid in base_skill_ids:
                    s_name, tooltip, _ = build_skill_display(sid)
                    safe_name = html.escape(s_name)
                    skill_chips.append(
                        "<span class=\"skill-pill tooltip\" tabindex=\"0\">"
                        + safe_name
                        + f"<span class=\"tooltip-content\"><strong>{safe_name}</strong><p>{tooltip}</p></span>"
                        + "</span>"
                    )

                plugin_icons: list[str] = []
                for plugin_idx, pid in enumerate(plugin_skill_ids):
                    p_name, tooltip, skill_def = build_skill_display(pid)
                    safe_name = html.escape(p_name)
                    icon_path = resolve_from_lookup(p_name, plugin_icon_lookup)
                    if not icon_path and skill_def:
                        icon_path = resolve_from_lookup(skill_def.get("id", ""), plugin_icon_lookup)
                    if not icon_path:
                        icon_path = resolve_from_lookup(pid, plugin_icon_lookup)
                    star_value = None
                    if plugin_idx < len(plugin_star_counts):
                        star_value = plugin_star_counts[plugin_idx]
                    icon_overlay = (
                        build_star_overlay_info(
                            icon_path,
                            is_plugin=True,
                            star_count=star_value,
                        )
                        if icon_path
                        else None
                    )
                    icon_uri = (
                        ensure_asset(icon_path, star_overlay=icon_overlay)
                        if icon_path
                        else None
                    )
                    icon_markup = (
                        f"<img src=\"{icon_uri}\" alt=\"{safe_name} icon\">"
                        if icon_uri
                        else f"<span class=\"plugin-fallback\">{safe_name}</span>"
                    )
                    plugin_icons.append(
                        "<div class=\"plugin-icon tooltip\" tabindex=\"0\">"
                        + icon_markup
                        + f"<span class=\"tooltip-content\"><strong>{safe_name}</strong><p>{tooltip}</p></span>"
                        + "</div>"
                    )

                hero_sections: list[str] = []
                hero_sections.append(
                    "<div class=\"hero-section\"><h5>Talents</h5>"
                    + (
                        "<div class=\"pill-list\">" + "".join(talent_chips) + "</div>"
                        if talent_chips
                        else "<p class=\"empty-state\">No talents selected.</p>"
                    )
                    + "</div>"
                )
                hero_sections.append(
                    "<div class=\"hero-section\"><h5>Skills</h5>"
                    + (
                        "<div class=\"pill-list\">" + "".join(skill_chips) + "</div>"
                        if skill_chips
                        else "<p class=\"empty-state\">No skills configured.</p>"
                    )
                    + "</div>"
                )
                hero_sections.append(
                    "<div class=\"hero-section\"><h5>Plugin Skills</h5>"
                    + (
                        "<div class=\"plugin-grid\">" + "".join(plugin_icons) + "</div>"
                        if plugin_icons
                        else "<p class=\"empty-state\">No plugin skills equipped.</p>"
                    )
                    + "</div>"
                )
                raw_gear_cfg: dict[str, Any] = {}
                if isinstance(hero_cfg, dict):
                    if isinstance(hero_cfg.get("gear"), dict):
                        raw_gear_cfg = dict(hero_cfg.get("gear", {}))
                    elif isinstance(hero_cfg.get("gear_ids"), dict):
                        raw_gear_cfg = dict(hero_cfg.get("gear_ids", {}))
                normalized_gear_cfg: dict[str, Any] = {}
                for slot_key, raw_value in raw_gear_cfg.items():
                    slot_name = normalize_gear_slot(slot_key)
                    if slot_name:
                        normalized_gear_cfg[slot_name] = raw_value

                gear_tiles: list[str] = []
                for slot_key, slot_label in GEAR_SLOT_ORDER:
                    slot_label_display = html.escape(slot_label)
                    raw_value = normalized_gear_cfg.get(slot_key)
                    gear_def = resolve_gear(raw_value) if raw_value else None
                    background_uri = (
                        gear_background_lookup.get(gear_def.rarity)
                        if gear_def and gear_def.rarity in gear_background_lookup
                        else None
                    )
                    icon_uri = None
                    if gear_def and os.path.exists(gear_def.icon_path):
                        icon_uri = ensure_asset(gear_def.icon_path)
                    if gear_def:
                        display_name = f"{gear_def.name} ({gear_def.rarity})"
                        safe_display_name = html.escape(display_name)
                        rarity_text = html.escape(gear_def.rarity)
                        effect_descs = list(gear_def.effect_descriptions())
                        effect_items = "".join(
                            f"<li>{html.escape(desc)}</li>" for desc in effect_descs
                        )
                        hero_label_text = normalize_metadata_text(raw_name) or raw_name
                        for desc in effect_descs:
                            short_desc = desc.split("(")[0].strip() or desc
                            gear_bonus_entries.append(
                                {
                                    "label": f"{gear_def.name} • {hero_label_text}",
                                    "value": short_desc,
                                }
                            )
                        effects_markup = (
                            f"<ul class=\"gear-effects\">{effect_items}</ul>"
                            if effect_items
                            else ""
                        )
                        tooltip_markup = (
                            f"<strong>{safe_display_name}</strong>"
                            + f"<p class=\"gear-meta\">Slot: {slot_label_display} • Rarity: {rarity_text}</p>"
                            + effects_markup
                            + "<p class=\"gear-tooltip-note\">Effects are permanent and additive.</p>"
                        )
                        tile_markup = (
                            "<div class=\"gear-slot tooltip\" tabindex=\"0\">"
                            + (
                                f"<img src=\"{background_uri}\" alt=\"\" class=\"gear-bg\">"
                                if background_uri
                                else ""
                            )
                            + (
                                f"<img src=\"{icon_uri}\" alt=\"{safe_display_name}\" class=\"gear-icon\">"
                                if icon_uri
                                else ""
                            )
                            + f"<span class=\"gear-slot-label\">{slot_label_display}</span>"
                            + f"<span class=\"tooltip-content\">{tooltip_markup}</span>"
                            + "</div>"
                        )
                    else:
                        fallback_text = (
                            html.escape(str(raw_value))
                            if raw_value not in (None, "")
                            else "None"
                        )
                        tile_markup = (
                            "<div class=\"gear-slot empty\">"
                            + f"<span class=\"gear-slot-label\">{slot_label_display}</span>"
                            + f"<span class=\"gear-empty-text\">{fallback_text}</span>"
                            + "</div>"
                        )
                    gear_tiles.append(tile_markup)

                hero_sections.append(
                    "<div class=\"hero-section\"><h5>Gear</h5>"
                    + (
                        "<div class=\"gear-grid\">" + "".join(gear_tiles) + "</div>"
                        if gear_tiles
                        else "<p class=\"empty-state\">No gear equipped.</p>"
                    )
                    + "</div>"
                )
                mount_entries: list[dict[str, Any]] = []
                if hero_idx < len(hero_skill_lists):
                    mount_entries = [
                        entry
                        for entry in hero_skill_lists[hero_idx] or []
                        if isinstance(entry, dict)
                        and _is_mount_skill(str(entry.get("id", "")))
                    ]

                if mount_entries:
                    mount_tiles: list[str] = []
                    for entry in mount_entries:
                        skill_id = str(entry.get("id", ""))
                        skill_name = normalize_metadata_text(entry.get("name")) or normalize_metadata_text(skill_id)
                        desc_raw = get_skill_description(skill_id, skill_name) if skill_id else None
                        desc = normalize_metadata_text(desc_raw) or "Skill details coming soon."
                        tooltip = html.escape(desc).replace("\n", "<br>")
                        icon_uri = resolve_skill_icon(skill_id, skill_name) or mount_placeholder or ""
                        display_name = html.escape(skill_name or "Mount Skill")
                        mount_tiles.append(
                            "<div class=\"tooltip mount-slot\" tabindex=\"0\">"
                            + (
                                f"<img src=\"{icon_uri}\" alt=\"{display_name}\">"
                                if icon_uri
                                else "<div class=\"placeholder-empty\"></div>"
                            )
                            + f"<span class=\"tooltip-content\"><strong>{display_name}</strong><p>{tooltip}</p></span>"
                            + "</div>"
                        )

                    hero_sections.append(
                        "<div class=\"hero-section\"><h5>Mount Skills</h5>"
                        + "<div class=\"mount-grid\">"
                        + "".join(mount_tiles)
                        + "</div></div>"
                    )
                else:
                    mount_slots = "".join(
                        (
                            f"<img src=\"{mount_placeholder}\" alt=\"Mount skill placeholder\">"
                            if mount_placeholder
                            else "<div class=\"placeholder-empty\"></div>"
                        )
                        for _ in range(2)
                    )
                    hero_sections.append(
                        "<div class=\"hero-section\"><h5>Mount Skills</h5>"
                        + "<div class=\"mount-grid\">"
                        + mount_slots
                        + "</div></div>"
                    )

                hero_cards.append(
                    "<div class=\"hero-card\">"
                    + "<div class=\"hero-header\">"
                    + portrait_html
                    + header_markup
                    + "</div>"
                    + "".join(hero_sections)
                    + "</div>"
                )

            if not hero_cards:
                hero_cards.append("<p class=\"empty-state\">No heroes configured.</p>")

            for entry in gear_bonus_entries:
                label_text = normalize_metadata_text(entry.get("label"))
                if not label_text:
                    label_text = str(entry.get("label", "Gear Bonus"))
                value_text = normalize_metadata_text(entry.get("value"))
                if not value_text:
                    value_text = str(entry.get("value", ""))
                bonus_entries.append({"label": label_text, "value": value_text})

            bonus_button_label = "Bonus Stats"
            if bonus_entries:
                bonus_button_label = f"Bonus Stats ({len(bonus_entries)})"

            bonus_data_attr = html.escape(json.dumps(bonus_entries, ensure_ascii=False))
            bonus_button_markup = ""
            if bonus_icon:
                bonus_button_markup = (
                    "<button class=\"bonus-button\" data-bonus='"
                    + bonus_data_attr
                    + "'>"
                    + (
                        f"<img src=\"{bonus_icon}\" alt=\"Bonus stats\">"
                        if bonus_icon
                        else ""
                    )
                    + f"<span>{html.escape(bonus_button_label)}</span></button>"
                )

            if bonus_entries:
                fallback_items = "".join(
                    (
                        "<li>"
                        + f"<span>{html.escape(entry['label'])}</span>"
                        + f"<strong>{html.escape(str(entry['value']))}</strong>"
                        + "</li>"
                    )
                    for entry in bonus_entries
                )
            else:
                fallback_items = "<li class=\"empty-state\">No bonus stats configured.</li>"
            bonus_fallback_markup = (
                "<ul class=\"bonus-fallback\">" + fallback_items + "</ul>"
            )

            if include_sample_details:
                history = sample_histories[idx] if idx < len(sample_histories) else {}
                unrevivable_series = history.get("unrevivable") if isinstance(history, dict) else None
                unrevivable_final = None
                if isinstance(unrevivable_series, list) and unrevivable_series:
                    last_val = unrevivable_series[-1]
                    try:
                        unrevivable_final = float(last_val)
                    except (TypeError, ValueError):
                        unrevivable_final = None
                if unrevivable_final is None and best_match_data:
                    key = "army1_unrevivable" if idx == 0 else "army2_unrevivable"
                    value = best_match_data.get(key)
                    if isinstance(value, (int, float)):
                        unrevivable_final = float(value)
                metrics_markup = "<div class=\"metric-list\">" + "".join(
                    (
                        "<div><span>{label}</span><strong>{value}</strong></div>".format(
                            label=html.escape(label), value=fmt_int(val)
                        )
                    )
                    for label, val in [
                        ("Initial Troops", summary_entry.get("initial")),
                        ("Remaining Troops", summary_entry.get("remaining")),
                        ("Heavily Wounded", unrevivable_final),
                        ("Healed Troops", summary_entry.get("healed")),
                        ("Total Kills", summary_entry.get("kills")),
                    ]
                ) + "</div>"

                hero_skill_sections: list[str] = []
                core_metric_meta = [
                    column for column in skill_columns if not column.get("is_boosted")
                ]
                boosted_metric_meta = [
                    column for column in skill_columns if column.get("is_boosted")
                ]
                for hero_idx, hero_skills in enumerate(hero_skill_lists):
                    hero_label = (
                        hero_names[hero_idx]
                        if hero_idx < len(hero_names)
                        else f"Hero {hero_idx + 1}"
                    )
                    valid_entries = [
                        entry for entry in (hero_skills or []) if isinstance(entry, dict)
                    ]
                    if not valid_entries:
                        hero_skill_sections.append(
                            "<div class=\"skill-hero\">"
                            + f"<h4>{html.escape(hero_label)}</h4>"
                            + "<p class=\"empty-state\">No skill data available.</p>"
                            + "</div>"
                        )
                        continue

                    metric_maxima: dict[str, float] = {
                        meta["key"]: 0.0 for meta in skill_columns
                    }
                    for entry in valid_entries:
                        for meta in skill_columns:
                            numeric_value = coerce_numeric(entry.get(meta["key"]))
                            if (
                                numeric_value is not None
                                and numeric_value > metric_maxima[meta["key"]]
                            ):
                                metric_maxima[meta["key"]] = numeric_value

                    def build_metric_items(
                        entry_dict: dict[str, Any],
                        metas: list[dict[str, Any]],
                    ) -> str:
                        items: list[str] = []
                        for meta in metas:
                            key = meta["key"]
                            label = meta.get("label") or key.title()
                            icon_path = meta.get("icon")
                            raw_value = entry_dict.get(key)
                            numeric_value = coerce_numeric(raw_value)
                            is_zero_like = False
                            if numeric_value is not None:
                                is_zero_like = abs(numeric_value) <= 1e-9
                            else:
                                if raw_value is None:
                                    is_zero_like = True
                                elif isinstance(raw_value, str):
                                    stripped = raw_value.strip()
                                    if not stripped:
                                        is_zero_like = True
                                    else:
                                        normalized = stripped.replace(",", "")
                                        if normalized.endswith("%"):
                                            normalized = normalized[:-1].strip()
                                        if not normalized:
                                            is_zero_like = True
                                        else:
                                            try:
                                                is_zero_like = (
                                                    abs(float(normalized)) <= 1e-9
                                                )
                                            except ValueError:
                                                is_zero_like = False
                                elif isinstance(raw_value, (int, float)):
                                    is_zero_like = abs(float(raw_value)) <= 1e-9
                            if is_zero_like:
                                continue
                            if key == "casts" and not isinstance(raw_value, (int, float)):
                                text = str(raw_value).strip() if raw_value is not None else ""
                                display_text = text if text else "—"
                            else:
                                display_text = fmt_int(raw_value)
                            max_value = metric_maxima.get(key, 0.0)
                            fill = 0.0
                            if numeric_value is not None and max_value > 0:
                                ratio = max(0.0, min(1.0, numeric_value / max_value))
                                fill = ratio
                            parts = ["<div class=\"skill-metric\">"]
                            header_bits: list[str] = ["<div class=\"metric-header\">"]
                            if icon_path:
                                header_bits.append(
                                    "<img src=\"{src}\" alt=\"{alt}\" class=\"metric-icon\" loading=\"lazy\">".format(
                                        src=html.escape(str(icon_path)),
                                        alt=html.escape(label),
                                    )
                                )
                            header_bits.append(
                                f"<span class=\"metric-label\">{html.escape(label)}</span>"
                            )
                            header_bits.append("</div>")
                            parts.append("".join(header_bits))
                            parts.append(
                                f"<span class=\"metric-value\">{html.escape(display_text)}</span>"
                            )
                            parts.append(
                                f"<span class=\"metric-bar\" style=\"--fill:{fill:.4f};\"></span>"
                            )
                            parts.append("</div>")
                            items.append("".join(parts))
                        return "".join(items)

                    skill_cards: list[str] = []
                    for entry in valid_entries:
                        skill_id = str(entry.get("id", ""))
                        skill_name = (
                            normalize_metadata_text(entry.get("name"))
                            or normalize_metadata_text(skill_id)
                            or "Skill"
                        )
                        desc_raw = get_skill_description(skill_id, skill_name) if skill_id else None
                        desc_text = normalize_metadata_text(desc_raw) or "Description unavailable."
                        tooltip = html.escape(desc_text).replace("\n", "<br>")
                        title_markup = html.escape(skill_name)
                        if tooltip:
                            title_markup = (
                                "<span class=\"tooltip\" tabindex=\"0\">"
                                + title_markup
                                + f"<span class=\"tooltip-content\"><strong>{title_markup}</strong><p>{tooltip}</p></span>"
                                + "</span>"
                            )
                        core_metrics_markup = build_metric_items(entry, core_metric_meta)
                        boosted_metrics_markup = (
                            build_metric_items(entry, boosted_metric_meta)
                            if boosted_metric_meta
                            else ""
                        )
                        card_parts = [
                            "<div class=\"skill-card\">",
                            "<header class=\"skill-card-header\">",
                            f"<h5 class=\"skill-card-title\">{title_markup}</h5>",
                            "</header>",
                            "<div class=\"skill-metric-grid\">",
                            core_metrics_markup or "<p class=\"empty-state\">No metrics available.</p>",
                            "</div>",
                        ]
                        if boosted_metrics_markup:
                            card_parts.append(
                                "<details class=\"skill-boosted\">"
                                + "<summary>Boosted Metrics</summary>"
                                + "<div class=\"skill-metric-grid\">"
                                + boosted_metrics_markup
                                + "</div>"
                                + "</details>"
                            )
                        card_parts.append("</div>")
                        skill_cards.append("".join(card_parts))

                    hero_skill_sections.append(
                        "<div class=\"skill-hero\">"
                        + f"<h4>{html.escape(hero_label)}</h4>"
                        + "<div class=\"skill-card-list\">"
                        + "".join(skill_cards)
                        + "</div>"
                        + "</div>"
                    )

                skill_block = (
                    "<div class=\"skill-breakdowns\">" + "".join(hero_skill_sections) + "</div>"
                )
                sample_army_blocks.append(
                    "<div class=\"sample-army-card\">"
                    + f"<h3>{html.escape(army_name)}</h3>"
                    + metrics_markup
                    + skill_block
                    + "</div>"
                )

            armies_html.append(
                "<section class=\"army-card\">"
                + "<header class=\"army-header\">"
                + "<div class=\"army-title\">"
                + (
                    f"<img src=\"{unit_icon}\" alt=\"{html.escape(unit_type)} icon\" class=\"unit-icon\">"
                    if unit_icon
                    else ""
                )
                + "<div>"
                + f"<h2>{html.escape(army_name)}</h2>"
                + f"<p>{html.escape(unit_type.title())} • Tier {tier} • {troop_count:,} troops</p>"
                + "</div></div>"
                + bonus_button_markup
                + bonus_fallback_markup
                + "</header>"
                + "<div class=\"section\"><h3>Army Info</h3><div class=\"stat-row\">"
                + "".join(stats_html)
                + "</div></div>"
                + "<div class=\"section\"><h3>Heroes</h3><div class=\"hero-grid\">"
                + "".join(hero_cards)
                + "</div></div>"
                + "<div class=\"section\"><h3>Jewels</h3><div class=\"jewel-grid\">"
                + "".join(jewel_cards)
                + "</div></div>"
                + "</section>"
            )

        if armies_html:
            armies_markup = "<section class=\"army-grid\">" + "".join(armies_html) + "</section>"
        else:
            armies_markup = ""

        own_troops_uri = histogram_lookup.get("own_remaining_troops.png")
        enemy_troops_uri = histogram_lookup.get("enemy_remaining_troops.png")

        def build_troops_panel(title: str, image_uri: str | None) -> str:
            safe_title = html.escape(title)
            if image_uri:
                alt_text = html.escape(f"{title} histogram")
                body = f"<img src=\"{image_uri}\" alt=\"{alt_text}\">"
            else:
                body = "<p class=\"graph-fallback\">Graph unavailable</p>"
            return (
                "<div class=\"victory-panel graph-panel\">"
                + f"<h3>{safe_title}</h3>"
                + body
                + "</div>"
            )

        def build_troop_history_panel() -> str:
            if not include_sample_details:
                return ""
            if not sample_histories:
                return (
                    "<div class=\"troop-history\">"
                    + "<h3>Remaining Troops Over Time</h3>"
                    + "<p class=\"graph-fallback\">History unavailable.</p>"
                    + "</div>"
                )
            max_points = max((len(hist.get("troops", [])) for hist in sample_histories), default=0)
            if max_points <= 1:
                return (
                    "<div class=\"troop-history\">"
                    + "<h3>Remaining Troops Over Time</h3>"
                    + "<p class=\"graph-fallback\">History unavailable.</p>"
                    + "</div>"
                )
            max_value = max(
                (
                    max(
                        (val for val in hist.get("troops", []) if isinstance(val, (int, float))),
                        default=0,
                    )
                    for hist in sample_histories
                ),
                default=0,
            )
            if max_value <= 0:
                max_value = 1
            width = 720
            height = 260
            pad_x = 56
            pad_y = 36
            x_step = (width - 2 * pad_x) / (max_points - 1)
            y_scale = (height - 2 * pad_y) / max_value if max_value else 1
            color_cycle = ["var(--accent-a)", "var(--accent-b)", "#3498db", "#9b59b6"]
            polylines: list[str] = []
            for idx, history in enumerate(sample_histories):
                troops = history.get("troops", []) or []
                if not troops:
                    continue
                points: list[str] = []
                last_val = troops[0]
                for point_idx in range(max_points):
                    if point_idx < len(troops):
                        last_val = troops[point_idx]
                    x = pad_x + point_idx * x_step
                    y_val = max(0.0, float(last_val))
                    y = height - pad_y - y_val * y_scale
                    points.append(f"{x:.2f},{y:.2f}")
                color = color_cycle[idx % len(color_cycle)]
                polylines.append(
                    f"<polyline class=\"chart-line\" fill=\"none\" stroke=\"{color}\" stroke-width=\"2.5\" points=\"{' '.join(points)}\"/>"
                )
            axis_markup = (
                f"<line class=\"chart-axis\" x1=\"{pad_x}\" y1=\"{height - pad_y}\" x2=\"{width - pad_x}\" y2=\"{height - pad_y}\"/>"
                + f"<line class=\"chart-axis\" x1=\"{pad_x}\" y1=\"{pad_y}\" x2=\"{pad_x}\" y2=\"{height - pad_y}\"/>"
            )
            round_count = max_points - 1
            label_markup = (
                f"<text class=\"chart-label\" x=\"{pad_x}\" y=\"{height - pad_y + 24}\">Round 0</text>"
                + f"<text class=\"chart-label\" x=\"{width - pad_x}\" y=\"{height - pad_y + 24}\" text-anchor=\"end\">Round {round_count}</text>"
                + f"<text class=\"chart-label\" x=\"{pad_x}\" y=\"{pad_y - 12}\" text-anchor=\"start\">{fmt_int(max_value)} troops</text>"
            )
            svg_markup = (
                f"<svg class=\"troop-chart-svg\" viewBox=\"0 0 {width} {height}\" role=\"img\" aria-label=\"Troop counts over {round_count} rounds\">"
                + axis_markup
                + "".join(polylines)
                + label_markup
                + "</svg>"
            )
            history_payload = {
                "armies": [
                    {
                        "name": history.get("name"),
                        "troops": list(history.get("troops", [])),
                        "unrevivable": list(history.get("unrevivable", [])),
                    }
                    for history in sample_histories
                ],
                "view_box": {"width": width, "height": height},
                "padding": {"x": pad_x, "y": pad_y},
                "point_count": max_points,
                "rounds": round_count,
            }
            data_json = json.dumps(history_payload).replace("</", "<\\/")
            data_markup = (
                "<script type=\"application/json\" id=\"troop-history-data\">"
                + data_json
                + "</script>"
            )
            legend_items = []
            swatch_classes = ["swatch-a", "swatch-b", "swatch-c", "swatch-d"]
            for idx, history in enumerate(sample_histories):
                name = html.escape(str(history.get("name", f"Army {idx + 1}")))
                legend_items.append(
                    f"<div class=\"legend-item\"><span class=\"swatch {swatch_classes[idx % len(swatch_classes)]}\"></span><span>{name}</span></div>"
                )
            legend_markup = "<div class=\"legend chart-legend\">" + "".join(legend_items) + "</div>"
            inspect_button_markup = (
                "<button type=\"button\" class=\"troop-inspect-btn\" data-role=\"troop-inspect\" aria-pressed=\"false\">"
                + "Inspect"
                + "</button>"
            )
            search_markup = (
                "<form class=\"troop-search\" data-role=\"troop-search\" autocomplete=\"off\">"
                + f"<label>Round <input type=\"number\" name=\"round\" min=\"0\" max=\"{round_count}\" value=\"{round_count}\"></label>"
                + "<button type=\"submit\">Go</button>"
                + "</form>"
            )
            chart_shell = (
                "<div class=\"troop-chart-shell\" tabindex=\"0\" role=\"application\" aria-label=\"Interactive troop history\">"
                + svg_markup
                + "<div class=\"troop-marker\" hidden></div>"
                + "<div class=\"troop-tooltip\" hidden><div class=\"troop-tooltip-content\"></div></div>"
                + "</div>"
            )
            return (
                "<div class=\"troop-history\">"
                + "<h3>Remaining Troops Over Time</h3>"
                + data_markup
                + "<div class=\"troop-chart-wrapper\">"
                + "<div class=\"troop-history-controls\">"
                + inspect_button_markup
                + search_markup
                + "</div>"
                + chart_shell
                + legend_markup
                + "</div></div>"
            )

        donut_style = f"--stop:{army_one_pct:.2f}%;"
        army_one_label = html.escape(army_one_name)
        army_two_label = html.escape(army_two_name)
        victory_sections = [
            "<section class=\"card victory-card\">",
            "<h2>Battle Overview</h2>",
            "<div class=\"victory-grid\">",
            build_troops_panel(f"{army_one_name} Troops Remaining", own_troops_uri),
            "<div class=\"victory-panel victory-summary\">",
            f"<div class=\"donut\" style=\"{donut_style}\" aria-hidden=\"true\">",
            "<div class=\"donut-inner\"></div></div>",
            "<div class=\"legend\">",
            f"<div class=\"legend-item\"><span class=\"swatch swatch-a\"></span><span>{army_one_label} ({army_one_pct:.1f}% • {army_one_wins} wins)</span></div>",
            f"<div class=\"legend-item\"><span class=\"swatch swatch-b\"></span><span>{army_two_label} ({army_two_pct:.1f}% • {army_two_wins} wins)</span></div>",
            "</div></div>",
            build_troops_panel(f"{army_two_name} Troops Remaining", enemy_troops_uri),
            "</div>",
        ]
        troop_history_markup = build_troop_history_panel()
        if troop_history_markup:
            victory_sections.append(troop_history_markup)
        victory_sections.append("</section>")
        victory_markup = "".join(victory_sections)

        sample_markup = ""
        if include_sample_details:
            battle_rounds = 0
            round_count_raw = sample_data_raw.get("round_count") if isinstance(sample_data_raw, dict) else None
            if isinstance(round_count_raw, (int, float)):
                try:
                    battle_rounds = int(round(float(round_count_raw)))
                except (TypeError, ValueError):
                    battle_rounds = 0
            if battle_rounds <= 0:
                battle_rounds = len(round_details)
            sample_seed = None
            if best_match_data and "seed" in best_match_data:
                sample_seed = best_match_data.get("seed")
            sample_winner = None
            if best_match_data and isinstance(best_match_data.get("winner"), int):
                winner_idx = int(best_match_data.get("winner", 0)) - 1
                if 0 <= winner_idx < len(army_names):
                    sample_winner = army_names[winner_idx]
            summary_items: list[tuple[str, str]] = []
            if battle_rounds:
                summary_items.append(("Battle Length", f"{battle_rounds} rounds"))
            if sample_seed not in (None, ""):
                summary_items.append(("Sample Seed", str(sample_seed)))
            if sample_winner:
                summary_items.append(("Sample Winner", sample_winner))
            if sample_army_blocks:
                army_block_markup = (
                    "<div class=\"sample-army-grid\">" + "".join(sample_army_blocks) + "</div>"
                )
            else:
                army_block_markup = (
                    "<div class=\"sample-army-grid\"><p class=\"empty-state\">No sample data available.</p></div>"
                )
            summary_markup = ""
            if summary_items:
                summary_markup = (
                    "<div class=\"sample-summary\"><ul class=\"sample-summary-metrics\">"
                    + "".join(
                        f"<li><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></li>"
                        for label, value in summary_items
                    )
                    + "</ul></div>"
                )
            ansi_escape_re = re.compile(r"\x1b\[[0-9;]*m")

            def strip_ansi_text(value: Any) -> str:
                text = normalize_metadata_text(value)
                return ansi_escape_re.sub("", text)

            def format_log_text(value: Any, preserve_breaks: bool = False) -> str:
                raw = strip_ansi_text(value).strip()
                if not raw:
                    return ""
                if preserve_breaks:
                    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
                    return "<br>".join(html.escape(part) for part in normalized.split("\n"))
                return html.escape(raw)

            battle_log_markup = ""
            if include_sample_log:
                troop_history_meta: list[tuple[str, list[int]]] = []
                if sample_histories:
                    for idx, history in enumerate(sample_histories):
                        label_text = strip_ansi_text(history.get("name"))
                        label_text = label_text.strip()
                        if not label_text:
                            label_text = (
                                army_names[idx]
                                if idx < len(army_names)
                                else f"Army {idx + 1}"
                            )
                        troops_series = history.get("troops") or []
                        troop_history_meta.append((label_text, troops_series))
                elif army_names:
                    for idx, label in enumerate(army_names):
                        troop_history_meta.append(
                            (strip_ansi_text(label).strip() or f"Army {idx + 1}", [])
                        )

                round_blocks: list[str] = []
                for idx, round_data in enumerate(round_details):
                    if not isinstance(round_data, dict):
                        continue
                    round_no = idx + 1
                    raw_round = round_data.get("round")
                    if isinstance(raw_round, (int, float)):
                        try:
                            round_no = int(round(float(raw_round)))
                        except (TypeError, ValueError):
                            round_no = idx + 1
                    else:
                        try:
                            round_no = int(round(float(raw_round)))
                        except (TypeError, ValueError):
                            round_no = idx + 1
                    if round_no < 1:
                        round_no = idx + 1
                    troop_badges: list[str] = []
                    for label_text, series in troop_history_meta:
                        start_value = 0.0
                        if series:
                            pos = idx if idx < len(series) else len(series) - 1
                            try:
                                raw_start = series[pos]
                            except (IndexError, TypeError, ValueError):
                                raw_start = 0
                            numeric_start = coerce_numeric(raw_start)
                            start_value = numeric_start if numeric_start is not None else 0.0
                        badge = (
                            "<span class=\"round-army\">"
                            + f"<span class=\"round-army-name\">{html.escape(label_text)}</span>"
                            + f"<strong>{html.escape(fmt_int(start_value))}</strong>"
                            + "</span>"
                        )
                        troop_badges.append(badge)
                    summary_html = "<summary><span class=\"round-label\">Round {}</span>".format(
                        html.escape(str(round_no))
                    )
                    if troop_badges:
                        summary_html += "<span class=\"round-counts\">" + "".join(troop_badges) + "</span>"
                    summary_html += "</summary>"

                    sections: list[str] = []

                    active_items: list[str] = []
                    for effect in round_data.get("active_effects") or []:
                        effect_html = format_log_text(effect, preserve_breaks=True)
                        if effect_html:
                            active_items.append(f"<li>{effect_html}</li>")
                    if active_items:
                        sections.append(
                            "<div class=\"log-section\"><h4>Active Effects</h4><ul>"
                            + "".join(active_items)
                            + "</ul></div>"
                        )

                    combat_rows: list[str] = []
                    for action in round_data.get("combat_actions") or []:
                        if not isinstance(action, dict):
                            continue
                        action_type_raw = strip_ansi_text(action.get("action_type", "")).strip()
                        log_line_raw = strip_ansi_text(action.get("log_line", "")).strip()
                        combined_checks = [
                            action_type_raw.lower() if action_type_raw else "",
                            log_line_raw.lower() if log_line_raw else "",
                        ]
                        if any("heavily wounded" in text for text in combined_checks if text):
                            continue
                        if any("damage commit" in text for text in combined_checks if text):
                            continue
                        attacker_raw = strip_ansi_text(action.get("attacker_name", "")).strip() or "Unknown"
                        defender_raw = strip_ansi_text(action.get("defender_name", "")).strip() or "Unknown"
                        metrics_html: list[str] = []
                        for key, label in (
                            ("damage_potential_hp", "Potential"),
                            ("absorbed_hp", "Absorbed"),
                            ("final_hp_damage", "Damage"),
                        ):
                            raw_val = action.get(key)
                            numeric_val = coerce_numeric(raw_val)
                            if numeric_val is None:
                                continue
                            metrics_html.append(
                                "<span class=\"combat-metric\"><span class=\"metric-label\">{label}</span><strong>{value}</strong></span>".format(
                                    label=html.escape(label),
                                    value=html.escape(fmt_int(raw_val)),
                                )
                            )
                        kills_val = coerce_numeric(action.get("potential_kills"))
                        if kills_val is not None and kills_val > 0:
                            metrics_html.append(
                                "<span class=\"combat-metric\"><span class=\"metric-label\">Kills</span><strong>{value}</strong></span>".format(
                                    value=html.escape(fmt_int(action.get("potential_kills")))
                                )
                            )
                        header_html = (
                            "<div class=\"combat-header\">"
                            + "<span class=\"combat-actors\">"
                            + f"<span class=\"combat-attacker\">{html.escape(attacker_raw)}</span>"
                            + "<span class=\"combat-arrow\">→</span>"
                            + f"<span class=\"combat-defender\">{html.escape(defender_raw)}</span>"
                            + "</span>"
                        )
                        if action_type_raw:
                            header_html += "<span class=\"combat-type\">{}</span>".format(
                                html.escape(action_type_raw)
                            )
                        header_html += "</div>"
                        combat_row_html = "<div class=\"combat-row\">" + header_html
                        if metrics_html:
                            combat_row_html += (
                                "<div class=\"combat-metrics\">" + "".join(metrics_html) + "</div>"
                            )
                        combat_row_html += "</div>"
                        combat_rows.append(combat_row_html)
                    if combat_rows:
                        sections.append(
                            "<div class=\"log-section\"><h4>Combat</h4><div class=\"combat-rows\">"
                            + "".join(combat_rows)
                            + "</div></div>"
                        )

                    skill_groups: list[str] = []
                    skill_data = round_data.get("skill_triggers")
                    if isinstance(skill_data, dict):
                        for army_label, triggers in skill_data.items():
                            group_label = strip_ansi_text(army_label).strip() or "Army"
                            entries: list[str] = []
                            if triggers:
                                for trig in triggers:
                                    if not isinstance(trig, dict):
                                        continue
                                    skill_name_clean = (
                                        strip_ansi_text(trig.get("skill_name", "")).strip()
                                    )
                                    effect_description_raw = trig.get("effect_description")
                                    effect_desc_clean = strip_ansi_text(
                                        effect_description_raw
                                    ).strip()
                                    if _should_skip_skill_trigger(
                                        skill_name_clean, effect_desc_clean
                                    ):
                                        continue
                                    skill_name = skill_name_clean or "Skill"
                                    effect_desc_html = format_log_text(
                                        effect_description_raw, preserve_breaks=True
                                    )
                                    detail_badges: list[str] = []
                                    for key, label in (
                                        ("damage_done_hp", "Damage"),
                                        ("shield_hp_gained", "Shield"),
                                        ("healed_hp", "Healed"),
                                        ("rage_generated", "Rage"),
                                        ("rage_reduced", "Rage Reduced"),
                                        ("rage_spent", "Rage Spent"),
                                        ("potential_kills", "Kills"),
                                    ):
                                        if key not in trig:
                                            continue
                                        raw_val = trig.get(key)
                                        numeric_val = coerce_numeric(raw_val)
                                        if numeric_val is None:
                                            continue
                                        if key == "potential_kills" and numeric_val <= 0:
                                            continue
                                        detail_badges.append(
                                            "<span class=\"skill-badge\">{label} <strong>{value}</strong></span>".format(
                                                label=html.escape(label),
                                                value=html.escape(fmt_int(raw_val)),
                                            )
                                        )
                                    entry_html_parts = [
                                        "<div class=\"skill-entry\">",
                                        f"<strong>{html.escape(skill_name)}</strong>",
                                    ]
                                    if effect_desc_html:
                                        entry_html_parts.append(
                                            f"<span class=\"skill-effect\">{effect_desc_html}</span>"
                                        )
                                    if detail_badges:
                                        entry_html_parts.append(
                                            "<div class=\"skill-detail\">" + "".join(detail_badges) + "</div>"
                                        )
                                    entry_html_parts.append("</div>")
                                    entries.append("".join(entry_html_parts))
                            if entries:
                                skill_groups.append(
                                    "<div class=\"skill-group\"><h5>{label}</h5>{entries}</div>".format(
                                        label=html.escape(group_label),
                                        entries="".join(entries),
                                    )
                                )
                            else:
                                skill_groups.append(
                                    "<div class=\"skill-group\"><h5>{label}</h5><p class=\"empty-state\">No skill triggers.</p></div>".format(
                                        label=html.escape(group_label)
                                    )
                                )
                    if skill_groups:
                        sections.append(
                            "<div class=\"log-section\"><h4>Skill Effects</h4><div class=\"skill-groups\">"
                            + "".join(skill_groups)
                            + "</div></div>"
                        )

                    if sections:
                        content_html = "<div class=\"round-content\">" + "".join(sections) + "</div>"
                    else:
                        content_html = (
                            "<div class=\"round-content\"><p class=\"empty-state\">No events recorded for this round.</p></div>"
                        )
                    round_blocks.append("<details class=\"round-log\">" + summary_html + content_html + "</details>")

                if round_blocks:
                    battle_log_markup = (
                        "<section class=\"card sample-log-card\"><h2>Sample Battle Log</h2><div class=\"round-log-list\">"
                        + "".join(round_blocks)
                        + "</div></section>"
                    )
                else:
                    battle_log_markup = (
                        "<section class=\"card sample-log-card\"><h2>Sample Battle Log</h2><p class=\"empty-state\">No round data available.</p></section>"
                    )

            sample_markup = (
                "<section class=\"card sample-card\">"
                + "<h2>Sample Battle Details</h2>"
                + summary_markup
                + army_block_markup
                + "</section>"
                + battle_log_markup
            )

        html_output = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{'Overall Performance &amp; Sample Battle' if include_sample_details else 'Overall Performance'} - {html.escape(army_names[0] if army_names else 'Army 1')} vs {html.escape(army_names[1] if len(army_names) > 1 else 'Army 2')}</title>
    <style>
        :root {{
            --bg: #080b16;
            --panel: #12192c;
            --panel-alt: #101726;
            --text: #f5f7ff;
            --muted: #9aa4c2;
            --accent-a: #2ecc71;
            --accent-b: #e74c3c;
            --border: rgba(255, 255, 255, 0.08);
            --card-radius: 18px;
            font-family: 'Segoe UI', Roboto, sans-serif;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            background: var(--bg);
            color: var(--text);
            padding: 40px 24px 80px;
        }}
        h1 {{
            font-size: 2.4rem;
            margin-bottom: 8px;
        }}
        h2 {{
            margin: 0;
            font-size: 1.6rem;
        }}
        h3 {{
            margin: 0 0 12px 0;
            font-size: 1.2rem;
        }}
        p {{
            margin: 0;
            color: var(--muted);
        }}
        main {{
            max-width: 1440px;
            margin: 0 auto;
            display: grid;
            gap: 24px;
        }}
        .header {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .card {{
            background: var(--panel);
            border-radius: var(--card-radius);
            padding: 24px;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border);
        }}
        .victory-card {{
            display: grid;
            gap: 24px;
            grid-column: 1 / -1;
            width: 100%;
        }}
        .victory-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 24px;
            align-items: stretch;
        }}
        .victory-panel {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            align-items: center;
            text-align: center;
            min-height: 100%;
        }}
        .victory-panel img {{
            width: 100%;
            height: auto;
            border-radius: 12px;
            background: #04060f;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }}
        .graph-panel {{
            width: 100%;
        }}
        .troop-history {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            margin-top: -4px;
            display: grid;
            gap: 16px;
        }}
        .troop-chart-wrapper {{
            position: relative;
            width: 100%;
            overflow: visible;
            display: grid;
            gap: 12px;
        }}
        .troop-history-controls {{
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .troop-search {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
        }}
        .troop-search label {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--muted);
            font-size: 0.85rem;
        }}
        .troop-search input {{
            width: 80px;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(0, 0, 0, 0.25);
            color: var(--text);
        }}
        .troop-search button {{
            padding: 6px 12px;
            border-radius: 6px;
            border: none;
            background: var(--accent-a);
            color: #04060f;
            font-weight: 600;
            cursor: pointer;
        }}
        .troop-search button:hover {{
            background: #27ae60;
        }}
        .troop-inspect-btn {{
            padding: 6px 16px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            background: rgba(255, 255, 255, 0.08);
            color: var(--text);
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
        }}
        .troop-inspect-btn:hover {{
            background: rgba(255, 255, 255, 0.14);
        }}
        .troop-inspect-btn.is-active {{
            background: var(--accent-a);
            border-color: transparent;
            color: #04060f;
        }}
        .troop-chart-shell {{
            position: relative;
            width: 100%;
            outline: none;
            cursor: default;
        }}
        .troop-chart-shell.is-inspecting {{
            cursor: crosshair;
        }}
        .troop-chart-shell:focus-visible {{
            box-shadow: 0 0 0 2px rgba(46, 204, 113, 0.6);
            border-radius: 12px;
        }}
        .troop-chart-svg {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .troop-history [hidden] {{
            display: none !important;
        }}
        .troop-marker {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: rgba(255, 255, 255, 0.65);
            box-shadow: 0 0 12px rgba(0, 0, 0, 0.6);
        }}
        .troop-marker::after {{
            content: '';
            position: absolute;
            inset-inline-start: 50%;
            transform: translateX(-50%);
            bottom: 36px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 0 16px rgba(0, 0, 0, 0.4);
        }}
        .troop-tooltip {{
            position: absolute;
            top: 0;
            inset-inline-start: 0;
            transform: translate(-50%, calc(-100% - 12px));
            min-width: 220px;
            max-width: 280px;
            background: rgba(8, 11, 22, 0.95);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px;
            box-shadow: 0 18px 30px rgba(0, 0, 0, 0.45);
            pointer-events: none;
            z-index: 20;
        }}
        .troop-tooltip-round {{
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .troop-tooltip-row {{
            display: flex;
            justify-content: flex-start;
            align-items: center;
            gap: 12px;
            margin-bottom: 4px;
        }}
        .troop-tooltip-label {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--muted);
        }}
        .troop-tooltip-value {{
            font-weight: 600;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            line-height: 1.2;
            gap: 2px;
        }}
        .troop-tooltip-remaining {{
            font-size: 0.875rem;
        }}
        .troop-tooltip-change {{
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--muted);
        }}
        .troop-tooltip-change.is-positive {{
            color: var(--accent-a);
        }}
        .troop-tooltip-change.is-negative {{
            color: #e74c3c;
        }}
        .troop-tooltip-subtext {{
            font-size: 0.75rem;
            color: var(--muted);
            margin: -2px 0 6px 24px;
        }}
        .chart-axis {{
            stroke: rgba(255, 255, 255, 0.25);
            stroke-width: 1.5;
        }}
        .chart-line {{
            stroke-linecap: round;
            stroke-linejoin: round;
        }}
        .chart-label {{
            fill: var(--muted);
            font-size: 0.75rem;
        }}
        .chart-legend {{
            justify-content: center;
        }}
        .victory-summary {{
            justify-content: center;
        }}
        .graph-fallback {{
            margin: 0;
            color: var(--muted);
            font-style: italic;
        }}
        .donut {{
            width: 220px;
            height: 220px;
            border-radius: 50%;
            background: conic-gradient(from 180deg, var(--accent-a) var(--stop), var(--accent-b) var(--stop));
            position: relative;
            overflow: hidden;
        }}
        .donut::after {{
            content: '';
            position: absolute;
            inset: 28px;
            background: var(--panel);
            border-radius: 50%;
            z-index: 0;
        }}
        .donut-inner {{
            position: absolute;
            inset: 28px;
            pointer-events: none;
            z-index: 1;
        }}
        .legend {{
            display: grid;
            gap: 10px;
            text-align: left;
            width: 100%;
        }}
        .legend-item {{
            display: flex;
            gap: 10px;
            align-items: center;
            color: var(--muted);
            justify-content: center;
        }}
        .swatch {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border-radius: 4px;
        }}
        .swatch-a {{ background: var(--accent-a); }}
        .swatch-b {{ background: var(--accent-b); }}
        .swatch-c {{ background: #3498db; }}
        .swatch-d {{ background: #9b59b6; }}
        .army-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 24px;
            align-items: start;
        }}
        .sample-card {{
            display: grid;
            gap: 24px;
        }}
        .sample-summary {{
            display: flex;
            justify-content: center;
        }}
        .sample-summary-metrics {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            gap: 18px;
            flex-wrap: wrap;
        }}
        .sample-summary-metrics li {{
            display: flex;
            gap: 10px;
            padding: 10px 16px;
            border-radius: 12px;
            background: var(--panel-alt);
            border: 1px solid var(--border);
            align-items: center;
        }}
        .sample-summary-metrics span {{
            color: var(--muted);
        }}
        .sample-summary-metrics strong {{
            font-weight: 600;
        }}
        .sample-army-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 24px;
            align-items: start;
        }}
        .sample-army-card {{
            background: var(--panel-alt);
            border-radius: var(--card-radius);
            border: 1px solid var(--border);
            padding: 24px;
            display: grid;
            gap: 18px;
        }}
        .sample-log-card {{
            display: grid;
            gap: 18px;
        }}
        .round-log-list {{
            display: grid;
            gap: 14px;
        }}
        .round-log {{
            border-radius: 16px;
            border: 1px solid var(--border);
            background: var(--panel-alt);
            overflow: hidden;
        }}
        .round-log > summary {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px 20px;
            cursor: pointer;
            list-style: none;
            font-weight: 600;
        }}
        .round-log > summary::-webkit-details-marker {{
            display: none;
        }}
        .round-log > summary::after {{
            content: "▾";
            font-size: 0.85rem;
            margin-inline-start: auto;
            transition: transform 0.2s ease;
            color: var(--muted);
        }}
        .round-log[open] > summary::after {{
            transform: rotate(180deg);
        }}
        .round-log[open] > summary {{
            background: rgba(255, 255, 255, 0.04);
            border-bottom: 1px solid var(--border);
        }}
        .round-label {{
            font-size: 1.05rem;
            letter-spacing: 0.02em;
        }}
        .round-counts {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-inline-start: auto;
        }}
        .round-army {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 4px 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.05);
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .round-army-name {{
            font-weight: 600;
            color: var(--text);
        }}
        .round-army strong {{
            color: var(--text);
            font-weight: 600;
        }}
        .round-content {{
            padding: 20px 22px 22px;
            display: grid;
            gap: 20px;
        }}
        .log-section {{
            display: grid;
            gap: 12px;
        }}
        .log-section h4 {{
            margin: 0;
            font-size: 1rem;
            letter-spacing: 0.03em;
        }}
        .log-section ul {{
            list-style: none;
            margin: 0;
            padding: 0;
            display: grid;
            gap: 8px;
        }}
        .log-section li {{
            padding: 10px 12px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            line-height: 1.4;
        }}
        .combat-rows {{
            display: grid;
            gap: 10px;
        }}
        .combat-row {{
            display: grid;
            gap: 10px;
            padding: 12px 14px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .combat-header {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 12px;
        }}
        .combat-actors {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.95rem;
        }}
        .combat-attacker,
        .combat-defender {{
            font-weight: 600;
        }}
        .combat-arrow {{
            color: var(--muted);
        }}
        .combat-type {{
            font-size: 0.8rem;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.08);
            color: var(--muted);
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .combat-metrics {{
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
        }}
        .combat-metric {{
            display: flex;
            flex-direction: column;
            gap: 2px;
            font-size: 0.8rem;
            color: var(--muted);
        }}
        .combat-metric strong {{
            font-size: 0.95rem;
            color: var(--text);
        }}
        .skill-groups {{
            display: grid;
            gap: 12px;
        }}
        .skill-group {{
            padding: 12px 14px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            display: grid;
            gap: 10px;
        }}
        .skill-group h5 {{
            margin: 0;
            font-size: 0.85rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }}
        .skill-entry {{
            display: grid;
            gap: 6px;
            padding: 10px 12px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .skill-entry strong {{
            font-size: 0.95rem;
        }}
        .skill-effect {{
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .skill-detail {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .skill-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.08);
            font-size: 0.78rem;
            color: var(--muted);
        }}
        .skill-badge strong {{
            color: var(--text);
            font-weight: 600;
        }}
        .metric-list {{
            margin: 0;
            display: grid;
            gap: 10px;
        }}
        .metric-list div {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 8px 12px;
        }}
        .metric-list span {{
            color: var(--muted);
            font-weight: 500;
        }}
        .metric-list strong {{
            font-weight: 600;
        }}
        .army-card {{
            background: var(--panel);
            border-radius: var(--card-radius);
            padding: 24px;
            border: 1px solid var(--border);
            display: grid;
            gap: 24px;
        }}
        .skill-breakdowns {{
            display: grid;
            gap: 16px;
        }}
        .skill-hero {{
            display: grid;
            gap: 14px;
        }}
        .skill-card-list {{
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        }}
        .skill-card {{
            background: linear-gradient(140deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: var(--card-radius);
            padding: 18px;
            box-shadow: 0 12px 32px rgba(12, 16, 22, 0.35);
            display: grid;
            gap: 16px;
            transition: box-shadow 0.3s ease, transform 0.3s ease;
        }}
        .skill-card:hover {{
            box-shadow: 0 16px 36px rgba(12, 16, 22, 0.42);
            transform: translateY(-2px);
        }}
        .skill-card-header {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 12px;
        }}
        .skill-card-icon {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--panel);
            padding: 6px;
        }}
        .skill-card-title {{
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            letter-spacing: 0.01em;
        }}
        .skill-metric-grid {{
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        }}
        .skill-metric {{
            position: relative;
            display: grid;
            gap: 6px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 12px 14px 16px;
        }}
        .skill-metric:hover {{
            border-color: rgba(255, 255, 255, 0.16);
        }}
        .metric-icon {{
            width: 18px;
            height: 18px;
            object-fit: contain;
            opacity: 0.85;
        }}
        .metric-header {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .metric-label {{
            color: var(--muted);
            font-size: 0.82rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .metric-value {{
            font-weight: 600;
            font-size: 1.05rem;
        }}
        .skill-metric .metric-bar {{
            position: relative;
            display: block;
            height: 4px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.08);
            overflow: hidden;
        }}
        .skill-metric .metric-bar::after {{
            content: "";
            position: absolute;
            inset: 0;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--accent-a), var(--accent-b));
            transform: scaleX(var(--fill, 0));
            transform-origin: left;
            transition: transform 0.3s ease;
        }}
        .skill-boosted {{
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 14px;
        }}
        .skill-boosted > summary {{
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 600;
            color: var(--accent-a);
            list-style: none;
        }}
        .skill-boosted > summary::-webkit-details-marker {{
            display: none;
        }}
        .skill-boosted > summary::after {{
            content: "▾";
            font-size: 0.75rem;
            transition: transform 0.2s ease;
        }}
        .skill-boosted[open] > summary::after {{
            transform: rotate(180deg);
        }}
        .skill-boosted .skill-metric-grid {{
            margin-top: 12px;
        }}
        .army-header {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .army-title {{
            display: flex;
            gap: 16px;
            align-items: center;
        }}
        .unit-icon {{
            width: 72px;
            height: 72px;
            object-fit: contain;
            background: var(--panel-alt);
            border-radius: 16px;
            padding: 12px;
            border: 1px solid var(--border);
        }}
        .bonus-button {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 18px;
            background: var(--panel-alt);
            color: var(--text);
            border-radius: 999px;
            border: 1px solid var(--border);
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s ease, background 0.2s ease;
        }}
        .bonus-button:hover {{
            background: #1a2236;
            transform: translateY(-1px);
        }}
        .bonus-button img {{
            width: 28px;
            height: 28px;
        }}
        .stat-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .stat-chip {{
            background: var(--panel-alt);
            padding: 12px 16px;
            border-radius: 14px;
            border: 1px solid var(--border);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
        }}
        .stat-chip img {{
            width: 22px;
            height: 22px;
        }}
        .stat-chip span {{
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .section {{
            display: grid;
            gap: 16px;
        }}
        .two-column {{
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        }}
        .jewel-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}
        .jewel-card {{
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 12px;
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        .jewel-card img {{
            width: 44px;
            height: 44px;
            object-fit: contain;
        }}
        .jewel-text {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .jewel-slot {{
            color: var(--muted);
            font-size: 0.85rem;
        }}
        .gear-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(84px, 1fr));
            gap: 12px;
            justify-content: center;
            justify-items: center;
            max-width: 260px;
            width: 100%;
            margin-inline: auto;
        }}
        .gear-slot {{
            position: relative;
            border: 1px solid var(--border);
            border-radius: 16px;
            background: var(--panel-alt);
            aspect-ratio: 1 / 1;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            width: 100%;
            max-width: 120px;
        }}
        .gear-slot .gear-bg {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0.9;
        }}
        .gear-slot .gear-icon {{
            position: absolute;
            inset: 27.5%;
            width: 45%;
            height: 45%;
            object-fit: contain;
            filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.45));
        }}
        .gear-slot .gear-slot-label {{
            position: absolute;
            top: 6px;
            left: 8px;
            padding: 2px 8px;
            border-radius: 999px;
            background: rgba(8, 11, 22, 0.7);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
        }}
        .gear-slot .gear-empty-text {{
            z-index: 1;
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .gear-slot.empty {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .gear-slot .tooltip-content {{
            max-width: 260px;
        }}
        .gear-meta {{
            margin: 6px 0 0;
            font-size: 0.8rem;
            color: var(--muted);
        }}
        .gear-effects {{
            margin: 10px 0 0;
            padding-left: 18px;
        }}
        .gear-effects li {{
            margin-bottom: 4px;
        }}
        .gear-tooltip-note {{
            margin-top: 10px;
            font-size: 0.75rem;
            color: var(--muted);
        }}
        .mount-grid {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 14px;
            margin-inline: auto;
        }}
        .mount-slot {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .mount-grid img,
        .mount-grid .placeholder-empty {{
            width: 60px;
            height: 60px;
            background: var(--panel-alt);
            border-radius: 14px;
            border: 1px solid var(--border);
        }}
        .mount-grid img {{
            padding: 8px;
            object-fit: contain;
        }}
        .mount-grid .placeholder-empty {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .hero-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 18px;
        }}
        .hero-card {{
            background: var(--panel-alt);
            border-radius: 18px;
            border: 1px solid var(--border);
            padding: 18px;
            display: grid;
            gap: 14px;
        }}
        .hero-header {{
            display: flex;
            gap: 16px;
            align-items: flex-start;
        }}
        .hero-portrait {{
            width: 88px;
            height: 88px;
            object-fit: contain;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: var(--panel);
            padding: 4px;
        }}
        .hero-header h4 {{
            margin: 0;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .hero-name {{
            font-weight: 600;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 2px 10px;
            border-radius: 999px;
            background: rgba(46, 204, 113, 0.18);
            border: 1px solid rgba(46, 204, 113, 0.35);
            color: var(--accent-a);
            font-size: 0.75rem;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }}
        .hero-section {{
            display: grid;
            gap: 8px;
        }}
        .hero-section h5 {{
            margin: 0;
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--muted);
        }}
        .pill-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .skill-pill {{
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            font-size: 0.85rem;
            color: var(--text);
            position: relative;
        }}
        .plugin-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
            justify-content: center;
            align-items: center;
            margin-inline: auto;
        }}
        .plugin-icon {{
            width: 120px;
            height: 120px;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.03);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 12px;
            position: relative;
            flex: 0 0 auto;
        }}
        .plugin-icon img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 16px;
        }}
        .plugin-fallback {{
            font-size: 0.75rem;
            color: var(--muted);
            text-align: center;
            line-height: 1.2;
        }}
        .tooltip {{
            position: relative;
        }}
        .tooltip-content {{
            position: absolute;
            inset-inline-start: 0;
            bottom: calc(100% + 10px);
            min-width: 240px;
            max-width: 320px;
            background: rgba(8, 11, 22, 0.95);
            border-radius: 12px;
            padding: 14px;
            border: 1px solid var(--border);
            box-shadow: 0 18px 30px rgba(0, 0, 0, 0.45);
            opacity: 0;
            transform: translateY(6px);
            transition: opacity 0.2s ease, transform 0.2s ease;
            pointer-events: none;
            z-index: 10;
        }}
        .tooltip-content p {{
            margin-top: 6px;
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .tooltip:hover .tooltip-content,
        .tooltip:focus .tooltip-content,
        .tooltip:focus-within .tooltip-content,
        .tooltip.touch-active .tooltip-content {{
            opacity: 1;
            transform: translateY(0);
            pointer-events: auto;
        }}
        .tooltip.touch-active {{
            z-index: 20;
        }}
        .empty-state {{
            color: var(--muted);
            font-style: italic;
        }}
        .modal {{
            position: fixed;
            inset: 0;
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 999;
        }}
        .modal.active {{
            display: flex;
        }}
        .modal-backdrop {{
            position: absolute;
            inset: 0;
            background: rgba(0, 0, 0, 0.65);
        }}
        .modal-content {{
            position: relative;
            background: var(--panel);
            padding: 28px;
            border-radius: 18px;
            border: 1px solid var(--border);
            width: min(480px, 90vw);
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 24px 40px rgba(0, 0, 0, 0.45);
        }}
        .modal-close {{
            position: absolute;
            top: 14px;
            right: 14px;
            background: transparent;
            border: none;
            color: var(--muted);
            font-size: 1.4rem;
            cursor: pointer;
        }}
        .bonus-fallback {{
            margin: 16px 0 0 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 8px;
        }}
        .bonus-fallback li {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 8px 12px;
            background: var(--panel-alt);
            border-radius: 10px;
            border: 1px solid var(--border);
        }}
        body.js .bonus-fallback {{
            display: none;
        }}
        .bonus-list {{
            list-style: none;
            margin: 24px 0 0 0;
            padding: 0;
            display: grid;
            gap: 10px;
        }}
        .bonus-list li {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            padding: 10px 14px;
            background: var(--panel-alt);
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        @media (max-width: 1100px) {{
            .victory-grid {{
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            }}
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 24px 16px 60px;
            }}
            main {{
                display: flex;
                flex-direction: column;
                gap: 24px;
            }}
            .army-grid {{
                display: flex;
                flex-direction: column;
                gap: 18px;
            }}
            .army-card {{
                min-width: 0;
            }}
            .hero-grid {{
                display: flex;
                flex-direction: column;
                gap: 18px;
            }}
            .hero-card {{
                min-width: 0;
            }}
            .hero-badge {{
                font-size: 0.7rem;
                padding: 2px 8px;
            }}
        }}
        @media (max-width: 820px) {{
            .victory-grid {{
                grid-template-columns: 1fr;
            }}
            .army-grid {{
                grid-template-columns: 1fr;
            }}
            .army-header {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <main>
        <header class=\"header\">
            <h1>{'Overall Performance &amp; Sample Battle' if include_sample_details else 'Overall Performance'}</h1>
            <p>Generated {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}</p>
        </header>
        {victory_markup}
        {armies_markup}
        {sample_markup}
    </main>
    <div class=\"modal\" id=\"bonus-modal\">
        <div class=\"modal-backdrop\"></div>
        <div class=\"modal-content\">
            <button class=\"modal-close\" aria-label=\"Close\">&times;</button>
            <h2>Bonus Stats</h2>
            <ul class=\"bonus-list\" id=\"bonus-list\"></ul>
        </div>
    </div>
    <script>
        if (document && document.body) {{
            document.body.classList.add('js');
        }}
        const enableTouchTooltips = () => {{
            const tooltipNodes = Array.from(document.querySelectorAll('.tooltip'));
            if (!tooltipNodes.length) {{
                return;
            }}
            const matchesHoverNone = window.matchMedia ? window.matchMedia('(hover: none)').matches : false;
            const isTouchCapable = matchesHoverNone
                || (navigator.maxTouchPoints || 0) > 0
                || 'ontouchstart' in window;
            if (!isTouchCapable) {{
                return;
            }}
            const clearActive = (except = null) => {{
                tooltipNodes.forEach((node) => {{
                    if (node !== except) {{
                        node.classList.remove('touch-active');
                    }}
                }});
            }};
            tooltipNodes.forEach((node) => {{
                if (!node.hasAttribute('tabindex')) {{
                    node.setAttribute('tabindex', '0');
                }}
                node.addEventListener('click', () => {{
                    const isActive = node.classList.contains('touch-active');
                    clearActive(node);
                    if (!isActive) {{
                        node.classList.add('touch-active');
                    }} else {{
                        node.classList.remove('touch-active');
                    }}
                }});
                node.addEventListener('keydown', (event) => {{
                    if (event.key === 'Escape') {{
                        node.classList.remove('touch-active');
                        node.blur();
                    }}
                }});
                node.addEventListener('blur', () => {{
                    node.classList.remove('touch-active');
                }});
            }});
            document.addEventListener('click', (event) => {{
                if (event.target.closest('.tooltip')) {{
                    return;
                }}
                clearActive();
            }});
        }};
        enableTouchTooltips();
        const modal = document.getElementById('bonus-modal');
        const modalList = document.getElementById('bonus-list');
        const closeModal = function () {{ modal.classList.remove('active'); }};
        modal.querySelector('.modal-backdrop').addEventListener('click', closeModal);
        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        document.addEventListener('keydown', function (evt) {{ if (evt.key === 'Escape') closeModal(); }});
        const openBonusModal = function (btn) {{
            const raw = btn.getAttribute('data-bonus') || '[]';
            let entries = [];
            try {{ entries = JSON.parse(raw); }} catch (err) {{ entries = []; }}
            modalList.innerHTML = '';
            if (!entries.length) {{
                const li = document.createElement('li');
                li.textContent = 'No bonus stats configured.';
                modalList.appendChild(li);
            }} else {{
                for (var idx = 0; idx < entries.length; idx += 1) {{
                    const entry = entries[idx];
                    const li = document.createElement('li');
                    const label = document.createElement('span');
                    label.textContent = entry.label || 'Bonus';
                    const value = document.createElement('strong');
                    value.textContent = entry.value || '0%';
                    li.appendChild(label);
                    li.appendChild(value);
                    modalList.appendChild(li);
                }}
            }}
            modal.classList.add('active');
        }};
        const hasTouchSupport = function () {{
            if (window.PointerEvent) {{
                return true;
            }}
            const navigatorRef = typeof navigator === 'undefined' ? null : navigator;
            return (
                'ontouchstart' in window ||
                (!!navigatorRef && 'maxTouchPoints' in navigatorRef && navigatorRef.maxTouchPoints > 0)
            );
        }};
        const buttons = document.querySelectorAll('.bonus-button');
        for (var btnIndex = 0; btnIndex < buttons.length; btnIndex += 1) {{
            const btn = buttons[btnIndex];
            if (!btn) {{
                continue;
            }}
            const open = function () {{ openBonusModal(btn); }};
            let pointerHandled = false;
            const handleClick = function () {{
                if (pointerHandled) {{
                    pointerHandled = false;
                    return;
                }}
                open();
            }};
            btn.addEventListener('click', handleClick);
            btn.addEventListener('keydown', function (event) {{
                if (event.key === 'Enter' || event.key === ' ') {{
                    event.preventDefault();
                    open();
                }}
            }});
            const markHandled = function () {{
                window.setTimeout(function () {{ pointerHandled = false; }}, 0);
            }};
            if (window.PointerEvent) {{
                btn.addEventListener(
                    'pointerup',
                    function (event) {{
                        if (event.pointerType === 'touch' || event.pointerType === 'pen') {{
                            pointerHandled = true;
                            event.preventDefault();
                            open();
                            markHandled();
                        }}
                    }},
                    {{ passive: false }}
                );
            }} else if (hasTouchSupport()) {{
                btn.addEventListener(
                    'touchend',
                    function (event) {{
                        pointerHandled = true;
                        event.preventDefault();
                        open();
                        markHandled();
                    }},
                    {{ passive: false }}
                );
            }}
        }}
        const initTroopHistory = () => {{
            const dataNode = document.getElementById('troop-history-data');
            if (!dataNode) {{
                return;
            }}
            let payload = null;
            try {{
                payload = JSON.parse(dataNode.textContent || dataNode.innerText || 'null');
            }} catch (err) {{
                payload = null;
            }}
            if (!payload || !Array.isArray(payload.armies) || !payload.armies.length) {{
                return;
            }}
            const root = dataNode.closest('.troop-history');
            if (!root) {{
                return;
            }}
            const shell = root.querySelector('.troop-chart-shell');
            const svg = root.querySelector('.troop-chart-svg');
            if (!shell || !svg) {{
                return;
            }}
            const marker = root.querySelector('.troop-marker');
            const tooltip = root.querySelector('.troop-tooltip');
            const tooltipContent = tooltip ? tooltip.querySelector('.troop-tooltip-content') : null;
            const searchForm = root.querySelector('.troop-search');
            const searchInput = searchForm ? searchForm.querySelector('input[name="round"]') : null;
            const inspectButton = root.querySelector('[data-role="troop-inspect"]');
            const viewBox = payload.view_box || {{}};
            const padding = payload.padding || {{}};
            const viewWidth = Number(viewBox.width) || 0;
            const padX = Number(padding.x) || 0;
            const pointCount = Math.max(0, Number(payload.point_count) || 0);
            const roundCount = Math.max(0, Number(payload.rounds) || Math.max(0, pointCount - 1));
            if (!viewWidth || pointCount <= 1) {{
                return;
            }}
            const swatchClasses = ['swatch-a', 'swatch-b', 'swatch-c', 'swatch-d'];
            const armies = payload.armies.map((entry, idx) => {{
                const name = typeof entry.name === 'string' && entry.name.trim().length
                    ? entry.name
                    : `Army ${{idx + 1}}`;
                return {{
                    name,
                    swatch: swatchClasses[idx % swatchClasses.length],
                    troops: Array.isArray(entry.troops) ? entry.troops.slice() : [],
                    unrevivable: Array.isArray(entry.unrevivable) ? entry.unrevivable.slice() : [],
                }};
            }});
            const expandSeries = (series) => {{
                const result = new Array(pointCount);
                let last = 0;
                for (let i = 0; i < pointCount; i += 1) {{
                    if (i < series.length) {{
                        const candidate = Number(series[i]);
                        if (Number.isFinite(candidate)) {{
                            last = candidate;
                        }}
                    }}
                    result[i] = last;
                }}
                return result;
            }};
            armies.forEach((army) => {{
                army.troops = expandSeries(army.troops);
                army.unrevivable = expandSeries(army.unrevivable);
            }});
            const step = pointCount > 1 ? (viewWidth - (padX * 2)) / (pointCount - 1) : 0;
            const clampRound = (round) => {{
                if (!Number.isFinite(round)) {{
                    return 0;
                }}
                const rounded = Math.round(round);
                return Math.min(Math.max(rounded, 0), pointCount - 1);
            }};
            const formatNumber = (value) => {{
                if (!Number.isFinite(value)) {{
                    return '0';
                }}
                const rounded = Math.round(value);
                return typeof rounded.toLocaleString === 'function' ? rounded.toLocaleString() : String(rounded);
            }};
            const formatDelta = (value) => {{
                if (!Number.isFinite(value) || value === 0) {{
                    return '0';
                }}
                const magnitude = formatNumber(Math.abs(value));
                return (value > 0 ? '+' : '-') + magnitude;
            }};
            const updateTooltip = (round) => {{
                if (!tooltip || !tooltipContent) {{
                    return;
                }}
                tooltipContent.innerHTML = '';
                const roundNode = document.createElement('div');
                roundNode.className = 'troop-tooltip-round';
                roundNode.textContent = `Round ${{round}}`;
                tooltipContent.appendChild(roundNode);
                armies.forEach((army) => {{
                    const row = document.createElement('div');
                    row.className = 'troop-tooltip-row';
                    const label = document.createElement('span');
                    label.className = 'troop-tooltip-label';
                    const swatch = document.createElement('span');
                    swatch.className = `swatch ${{army.swatch}}`;
                    label.appendChild(swatch);
                    label.appendChild(document.createTextNode(army.name));
                    const value = document.createElement('span');
                    value.className = 'troop-tooltip-value';
                    const troopValue = Number(army.troops[round]);
                    const remaining = Number.isFinite(troopValue) ? troopValue : 0;
                    const remainingNode = document.createElement('span');
                    remainingNode.className = 'troop-tooltip-remaining';
                    remainingNode.textContent = `Remaining: ${{formatNumber(remaining)}}`;
                    value.appendChild(remainingNode);
                    const previousValue = round > 0 ? Number(army.troops[round - 1]) : remaining;
                    const deltaValue = Number.isFinite(previousValue) ? remaining - previousValue : 0;
                    const changeNode = document.createElement('span');
                    changeNode.className = 'troop-tooltip-change';
                    changeNode.textContent = `Change: ${{formatDelta(deltaValue)}}`;
                    if (deltaValue > 0) {{
                        changeNode.classList.add('is-positive');
                    }} else if (deltaValue < 0) {{
                        changeNode.classList.add('is-negative');
                    }}
                    value.appendChild(changeNode);
                    row.appendChild(label);
                    row.appendChild(value);
                    tooltipContent.appendChild(row);
                    const unrevivableValue = Number(army.unrevivable[round]);
                    if (Number.isFinite(unrevivableValue) && unrevivableValue > 0) {{
                        const sub = document.createElement('div');
                        sub.className = 'troop-tooltip-subtext';
                        sub.textContent = `Unrevivable: ${{formatNumber(unrevivableValue)}}`;
                        tooltipContent.appendChild(sub);
                    }}
                }});
            }};
            const positionMarker = (round) => {{
                if (!marker) {{
                    return;
                }}
                const rect = shell.getBoundingClientRect();
                if (!rect || !rect.width) {{
                    return;
                }}
                const x = padX + round * step;
                const ratio = rect.width / viewWidth;
                const offset = Math.max(0, Math.min(rect.width, x * ratio));
                marker.style.transform = `translateX(${{offset}}px)`;
                marker.hidden = false;
                if (tooltip) {{
                    tooltip.style.left = `${{offset}}px`;
                    tooltip.hidden = false;
                }}
            }};
            let currentRound = clampRound(roundCount);
            if (searchInput) {{
                searchInput.value = String(currentRound);
            }}
            let inspectEnabled = false;
            const refreshRoundDisplay = () => {{
                if (inspectEnabled) {{
                    positionMarker(currentRound);
                    updateTooltip(currentRound);
                }} else {{
                    if (marker) {{
                        marker.hidden = true;
                    }}
                    if (tooltip) {{
                        tooltip.hidden = true;
                    }}
                }}
            }};
            const setInspectEnabled = (enabled) => {{
                inspectEnabled = enabled;
                if (inspectButton) {{
                    inspectButton.classList.toggle('is-active', inspectEnabled);
                    inspectButton.setAttribute('aria-pressed', inspectEnabled ? 'true' : 'false');
                }}
                shell.classList.toggle('is-inspecting', inspectEnabled);
                refreshRoundDisplay();
            }};
            const showRound = (round) => {{
                currentRound = clampRound(round);
                if (searchInput) {{
                    searchInput.value = String(Math.min(currentRound, roundCount));
                }}
                refreshRoundDisplay();
            }};
            const getRoundFromPointer = (clientX) => {{
                const rect = shell.getBoundingClientRect();
                if (!rect || !rect.width) {{
                    return currentRound;
                }}
                const relative = clientX - rect.left;
                const viewX = (relative / rect.width) * viewWidth;
                const raw = step ? (viewX - padX) / step : 0;
                return clampRound(raw);
            }};
            shell.addEventListener('pointermove', (event) => {{
                if (!inspectEnabled) {{
                    return;
                }}
                if (event.pointerType === 'mouse' || event.pressure > 0 || event.buttons > 0) {{
                    showRound(getRoundFromPointer(event.clientX));
                }}
            }});
            shell.addEventListener('pointerdown', (event) => {{
                shell.focus({{ preventScroll: true }});
                if (!inspectEnabled) {{
                    return;
                }}
                showRound(getRoundFromPointer(event.clientX));
            }});
            shell.addEventListener('pointerup', (event) => {{
                if (!inspectEnabled) {{
                    return;
                }}
                showRound(getRoundFromPointer(event.clientX));
            }});
            shell.addEventListener('keydown', (event) => {{
                if (!inspectEnabled) {{
                    return;
                }}
                if (event.key === 'ArrowLeft') {{
                    event.preventDefault();
                    showRound(currentRound - 1);
                }} else if (event.key === 'ArrowRight') {{
                    event.preventDefault();
                    showRound(currentRound + 1);
                }} else if (event.key === 'Home') {{
                    event.preventDefault();
                    showRound(0);
                }} else if (event.key === 'End') {{
                    event.preventDefault();
                    showRound(pointCount - 1);
                }} else if (event.key === 'PageUp') {{
                    event.preventDefault();
                    showRound(currentRound - 5);
                }} else if (event.key === 'PageDown') {{
                    event.preventDefault();
                    showRound(currentRound + 5);
                }}
            }});
            if (searchForm && searchInput) {{
                searchForm.addEventListener('submit', (event) => {{
                    event.preventDefault();
                    const value = Number(searchInput.value);
                    if (Number.isFinite(value)) {{
                        showRound(value);
                        shell.focus({{ preventScroll: true }});
                    }}
                }});
                searchInput.addEventListener('change', () => {{
                    const value = Number(searchInput.value);
                    if (Number.isFinite(value)) {{
                        showRound(value);
                    }}
                }});
            }}
            if (inspectButton) {{
                inspectButton.addEventListener('click', () => {{
                    const nextState = !inspectEnabled;
                    setInspectEnabled(nextState);
                    if (nextState) {{
                        shell.focus({{ preventScroll: true }});
                    }}
                }});
            }}
            window.addEventListener('resize', () => {{
                if (!inspectEnabled) {{
                    return;
                }}
                positionMarker(currentRound);
                updateTooltip(currentRound);
            }});
            setInspectEnabled(false);
        }};
        initTroopHistory();
    </script>
</body>
</html>
"""

        try:
            with open(save_path, "w", encoding="utf-8") as fh:
                fh.write(html_output)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to write export files: {exc}",
            )
            return

        self.last_setup_dir = os.path.dirname(save_path)
        self.status.setText(f"HTML summary exported to {os.path.basename(save_path)}")

    def export_summary_html(self) -> None:
        self._export_summary_html(
            include_sample_details=False,
            include_sample_log=True,
            dialog_title="Export Overall Performance HTML",
            filename_suffix="overall_performance",
        )

    def export_summary_with_sample_html(self) -> None:
        self._export_summary_html(
            include_sample_details=True,
            include_sample_log=True,
            dialog_title="Export Overall Performance & Sample Battle HTML",
            filename_suffix="overall_performance_sample",
        )

    def export_summary_with_sample_summary_html(self) -> None:
        self._export_summary_html(
            include_sample_details=True,
            include_sample_log=False,
            dialog_title="Export Overall Performance & Sample Battle Summary HTML",
            filename_suffix="overall_performance_sample_summary",
        )

    def export_pdf(self) -> None:
        """Export a multi-page PDF using the configured layout."""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            self.last_setup_dir,
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return
        writer = QtGui.QPdfWriter(file_path)
        painter = QtGui.QPainter(writer)
        for page_idx, page in enumerate(self.pdf_layout):
            page_width = writer.width()
            page_height = writer.height()
            gradient = QtGui.QLinearGradient(0, 0, 0, page_height)
            gradient.setColorAt(0, QtGui.QColor("#4a4a4a"))
            gradient.setColorAt(1, QtGui.QColor("#1e1e1e"))
            painter.fillRect(0, 0, page_width, page_height, gradient)
            for item in page.get("items", []):
                pix = self.get_pdf_item_pixmap(item.get("type", ""))
                if pix is None:
                    continue
                scale = float(item.get("scale", 1.0))
                if scale != 1.0:
                    pix = pix.scaled(
                        int(pix.width() * scale),
                        int(pix.height() * scale),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                x = int(item.get("x", 0))
                y = int(item.get("y", 0))
                painter.drawPixmap(x, y, pix)
            if page_idx < len(self.pdf_layout) - 1:
                writer.newPage()
        painter.end()
        self.status.setText(f"PDF exported to {os.path.basename(file_path)}")

    # --- Simulation handling --------------------------------------------
    def run_simulation(self) -> None:
        worker = getattr(self, "worker", None)
        if worker:
            try:
                if worker.isRunning():
                    worker.cancel()
                    self.run_btn.setText("Run Simulation")
                    self.run_btn.setEnabled(True)
                    return
            except RuntimeError:
                self.worker = None

        setup_data = [self.army1_frame.build_config(), self.army2_frame.build_config()]
        self._ensure_unique_army_names(setup_data)
        self._last_setup_data = [copy.deepcopy(cfg) for cfg in setup_data]
        self._last_simulation_payload = None
        runs = self.runs_spin.value()
        workers = self.workers_spin.value()
        self.status.setText("Running simulation...")
        self._set_skill_breakdown_message("Generating skill breakdowns…")
        self.progress.setRange(0, runs)
        self.progress.setValue(0)
        self.run_btn.setText("Cancel")
        self._dynamic_unrevivable_settings = dynamic_unrevivable_config.get_settings()
        self.worker = SimulationWorker(
            setup_data,
            runs,
            workers,
            self.seed_target,
            dynamic_settings=self._dynamic_unrevivable_settings,
            hero_cooldowns_enabled=self.hero_cooldowns_enabled,
            plugin_cooldowns_enabled=self.plugin_cooldowns_enabled,
            gem_cooldowns_enabled=self.gem_cooldowns_enabled,
            mount_cooldowns_enabled=self.mount_cooldowns_enabled,
        )
        self.worker.progress_update.connect(
            lambda d, t: (self.progress.setMaximum(t), self.progress.setValue(d))
        )
        self.worker.finished_text.connect(self._sim_finished)
        self.worker.error.connect(self._sim_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _ensure_unique_army_names(self, configs: list[dict[str, Any]]) -> None:
        seen: set[str] = set()
        frames = [self.army1_frame, self.army2_frame]
        for cfg, frame in zip(configs, frames):
            base_name = cfg.get("army_name") or f"Army {frame.index}"
            candidate = base_name
            suffix = 2
            while candidate in seen:
                candidate = f"{base_name} ({suffix})"
                suffix += 1
            seen.add(candidate)
            if candidate != base_name:
                cfg["army_name"] = candidate
                if frame.name_edit.text() != candidate:
                    frame.name_edit.setText(candidate)

    def _populate_round_tree(
        self, rounds: list[dict], tree: QtWidgets.QTreeWidget | None = None
    ) -> None:
        target = tree or self.output_tree
        target.clear()
        for r in rounds:
            title = f"Round {r['round']}"
            if r.get("defender_global_round") is not None:
                title += f" (Defender Round {r['defender_global_round']})"
            round_item = QtWidgets.QTreeWidgetItem([title])
            if r.get("active_effects"):
                effects_item = QtWidgets.QTreeWidgetItem(["Active Effects"])
                for eff in r["active_effects"]:
                    QtWidgets.QTreeWidgetItem(effects_item, [eff])
                round_item.addChild(effects_item)
            if r.get("combat_actions"):
                actions_item = QtWidgets.QTreeWidgetItem(["Combat Actions"])
                for a in r["combat_actions"]:
                    desc = (
                        f"{a['attacker_name']} -> {a['defender_name']} {a['action_type']}"
                        f" DMG Pot {a['damage_potential_hp']:.0f} Absorb {a['absorbed_hp']:.0f}"
                        f" Final {a['final_hp_damage']:.0f} Kills {a['potential_kills']}"
                    )
                    QtWidgets.QTreeWidgetItem(actions_item, [desc])
                round_item.addChild(actions_item)
            for army_name, triggers in r.get("skill_triggers", {}).items():
                army_item = QtWidgets.QTreeWidgetItem([f"{army_name} Skill Triggers"])
                if not triggers:
                    QtWidgets.QTreeWidgetItem(army_item, ["None"])
                else:
                    for tr in triggers:
                        detail = ""
                        if "damage_done_hp" in tr:
                            detail = f" DMG {tr['damage_done_hp']:.0f}"
                        elif "shield_hp_gained" in tr:
                            detail = f" Shield {tr['shield_hp_gained']:.0f}"
                        if tr.get("potential_kills"):
                            detail += f" Kills {tr['potential_kills']}"
                        text = f"{tr['skill_name']}: {tr['effect_description']}{detail}"
                        QtWidgets.QTreeWidgetItem(army_item, [text])
                round_item.addChild(army_item)
            target.addTopLevelItem(round_item)

    def _sim_finished(
        self, text: str, rounds: list[dict], summary: list[dict] | None
    ) -> None:
        self.output_text.setPlainText(text)
        self._populate_round_tree(rounds)
        display_histograms(
            self.hist_scroll,
            self.army1_frame.name_edit.text() or f"Army 1",
            self.army2_frame.name_edit.text() or f"Army 2",
        )
        if summary:
            self.update_skill_breakdowns(summary)
        else:
            message = self._skill_breakdown_default_message
            if text.strip().lower().startswith("simulation cancelled"):
                message = "Simulation cancelled."
            self._set_skill_breakdown_message(message)
        export_payload: dict[str, Any] | None = None
        worker = getattr(self, "worker", None)
        win_rate = getattr(worker, "win_rate", None) if worker else None
        runs = getattr(worker, "runs", self.runs_spin.value())
        best_match = getattr(worker, "best_match", None) if worker else None
        sample_stats = getattr(worker, "sample_battle_stats", None) if worker else None
        setup_data = self._last_setup_data or [
            self.army1_frame.build_config(),
            self.army2_frame.build_config(),
        ]
        if summary and win_rate is not None:
            export_payload = {
                "report_text": text,
                "rounds": rounds,
                "summary": copy.deepcopy(summary),
                "win_rate": float(win_rate),
                "runs": int(runs),
                "best_match": copy.deepcopy(best_match) if isinstance(best_match, dict) else None,
                "setup": [copy.deepcopy(cfg) for cfg in setup_data],
                "histograms": self._collect_histogram_images(),
                "generated_at": time.time(),
                "army_names": [
                    self.army1_frame.name_edit.text() or "Army 1",
                    self.army2_frame.name_edit.text() or "Army 2",
                ],
                "cooldown_settings": {
                    "hero": self.hero_cooldowns_enabled,
                    "plugin": self.plugin_cooldowns_enabled,
                    "gem": self.gem_cooldowns_enabled,
                    "mount": self.mount_cooldowns_enabled,
                },
            }
            if isinstance(sample_stats, dict):
                export_payload["sample_battle"] = copy.deepcopy(sample_stats)
        self._last_simulation_payload = export_payload
        self.progress.setValue(0)
        self.status.setText("Ready")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Simulation")
        self.worker = None

    def _sim_error(self, msg: str) -> None:  # pragma: no cover - GUI feedback
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.progress.setValue(0)
        self.status.setText("Ready")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Simulation")
        self.worker = None


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

