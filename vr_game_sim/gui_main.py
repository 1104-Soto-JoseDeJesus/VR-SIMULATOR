"""PyQt6 based GUI for configuring and running battles."""

from __future__ import annotations

import os
from typing import Any, Callable
import threading
import math
import json
from functools import partial
import time
import re
import concurrent.futures

from PyQt6 import QtCore, QtGui, QtWidgets
import shutil
from PIL import Image, ImageQt
import numpy as np
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.unit_definition import Unit
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
)
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL, SkillType
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.arena_engine import ArenaEngine
from vr_game_sim.navmesh import NavMesh
from vr_game_sim.gui.arena_stats import HeroStatsWidget, HeroStatsHeader


def get_pdf_layout_path() -> str:
    """Return path for persisted PDF layout configuration."""
    return os.path.join(os.path.dirname(__file__), "pdf_layout.json")


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
        self.vert_spin.setSingleStep(0.01)
        self.vert_spin.setDecimals(3)
        form.addRow("Vertical Ratio", self.vert_spin)

        self.side_spin = QtWidgets.QDoubleSpinBox()
        self.side_spin.setRange(0.0, 0.5)
        self.side_spin.setSingleStep(0.01)
        self.side_spin.setDecimals(3)
        form.addRow("Side Margin Ratio", self.side_spin)

        v_offsets_layout = QtWidgets.QHBoxLayout()
        self.v_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            v_offsets_layout.addWidget(spin)
            self.v_offset_spins.append(spin)
        form.addRow("Hero V Offsets", v_offsets_layout)

        h_offsets_layout = QtWidgets.QHBoxLayout()
        self.h_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            h_offsets_layout.addWidget(spin)
            self.h_offset_spins.append(spin)
        form.addRow("Hero H Offsets", h_offsets_layout)

        sizes_layout = QtWidgets.QHBoxLayout()
        self.size_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.1, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            spin.setValue(1.0)
            sizes_layout.addWidget(spin)
            self.size_spins.append(spin)
        form.addRow("Hero Size Factors", sizes_layout)

        plugin_v_layout = QtWidgets.QHBoxLayout()
        self.plugin_v_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            plugin_v_layout.addWidget(spin)
            self.plugin_v_offset_spins.append(spin)
        form.addRow("Plugin V Offsets", plugin_v_layout)

        plugin_h_layout = QtWidgets.QHBoxLayout()
        self.plugin_h_offset_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-2.0, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
            plugin_h_layout.addWidget(spin)
            self.plugin_h_offset_spins.append(spin)
        form.addRow("Plugin H Offsets", plugin_h_layout)

        plugin_size_layout = QtWidgets.QHBoxLayout()
        self.plugin_size_spins: list[QtWidgets.QDoubleSpinBox] = []
        for _ in range(6):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.1, 2.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(3)
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

class SkillParamEditor(QtWidgets.QWidget):
    """Widget providing spin boxes for configurable skill parameters."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QtWidgets.QFormLayout(self)
        self._fields: dict[tuple[str, ...], QtWidgets.QDoubleSpinBox] = {}
        self._defaults: dict[tuple[str, ...], float] = {}
        self._skill_id: str | None = None

    def set_skill(self, skill_id: str | None, overrides: dict | None = None) -> None:
        """Populate editors for ``skill_id`` using optional ``overrides``."""
        # Save current overrides before switching
        self.clear()
        self._skill_id = skill_id or None
        if not skill_id:
            return
        sdef = SKILL_REGISTRY_GLOBAL.get(skill_id)
        if not sdef:
            return
        overrides = overrides or {}
        # Trigger chance
        tc = sdef.get("trigger_chance")
        if isinstance(tc, (int, float)):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.01)
            spin.setValue(overrides.get("trigger_chance", tc))
            self._layout.addRow("Trigger Chance", spin)
            self._fields[("trigger_chance",)] = spin
            self._defaults[("trigger_chance",)] = float(tc)
        # Config numeric entries
        cfg = sdef.get("config", {})
        override_cfg = overrides.get("config", {})
        if isinstance(cfg, dict):
            for key, val in cfg.items():
                if isinstance(val, (int, float)):
                    spin = QtWidgets.QDoubleSpinBox()
                    spin.setRange(-1e9, 1e9)
                    spin.setDecimals(3)
                    spin.setValue(override_cfg.get(key, float(val)))
                    self._layout.addRow(key.replace("_", " ").title(), spin)
                    self._fields[("config", key)] = spin
                    self._defaults[("config", key)] = float(val)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields.clear()
        self._defaults.clear()

    def get_overrides(self) -> dict:
        overrides: dict = {}
        for path, spin in self._fields.items():
            val = float(spin.value())
            default = self._defaults.get(path)
            if default is None or val == default:
                continue
            d = overrides
            for key in path[:-1]:
                d = d.setdefault(key, {})
            d[path[-1]] = val
        return overrides


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
        self.talent_param_editors: list[SkillParamEditor] = []
        self.base_param_editors: list[SkillParamEditor] = []
        self.plugin_param_editors: list[SkillParamEditor] = []
        overrides_map = hero_config.get("skill_overrides", {}) if hero_config else {}

        talent_opts = _skill_options(SkillType.TALENT)
        base_opts = _skill_options(SkillType.BASE_SKILL)
        plugin_opts = _skill_options(SkillType.PLUGIN_SKILL)

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
        return {
            "hero_name_or_preset": self.name_edit.text().strip(),
            "talent_ids": [box.currentData() or "" for box in self.talent_boxes],
            "base_skill_ids": [box.currentData() or "" for box in self.base_boxes if box.currentText() != "None"],
            "plugin_skill_ids": [box.currentData() or "" for box in self.plugin_boxes if box.currentText() != "None"],
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
        self.hero_overrides: dict[int, dict] = {1: {}, 2: {}}
        self._hero_names: dict[int, str] = {1: "None", 2: "None"}

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

    def edit_hero(self, slot: int) -> None:
        """Open the hero editor and persist changes.

        Skill parameter overrides are stored separately so that preset heroes
        can be tweaked without converting them into full custom entries.
        """
        current_cfg = self.custom_heroes.get(slot)
        hero_name = self.hero1_combo.currentText() if slot == 1 else self.hero2_combo.currentText()
        if current_cfg is None:
            preset = HERO_PRESETS.get(hero_name.lower())
            if preset:
                current_cfg = {
                    "hero_name_or_preset": hero_name,
                    "talent_ids": preset.get("talents", []),
                    "base_skill_ids": preset.get("base_skills", []),
                    "plugin_skill_ids": preset.get("plugin_skills", []),
                }
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
                preset = HERO_PRESETS.get(name.lower())
                if (
                    preset
                    and preset.get("talents", []) == cfg.get("talent_ids")
                    and preset.get("base_skills", []) == cfg.get("base_skill_ids")
                    and preset.get("plugin_skills", []) == cfg.get("plugin_skill_ids")
                ):
                    self.custom_heroes[slot] = None
                else:
                    self.custom_heroes[slot] = cfg
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
        cfg = self.custom_heroes.get(slot)
        if prev_name != name:
            # Changing heroes discards any overrides from the previous selection.
            self.hero_overrides[slot] = {}
            if cfg and cfg.get("hero_name_or_preset") != name and name not in {"None", "Custom"}:
                self.custom_heroes[slot] = None
        self._hero_names[slot] = name

        img_label = self.hero1_img if slot == 1 else self.hero2_img
        img_label.set_image(None)
        img_label.setToolTip(name if name not in {"None", "Custom"} else "")
        plugin_labels = self.hero1_plugin_imgs if slot == 1 else self.hero2_plugin_imgs
        for lbl in plugin_labels:
            lbl.set_image(None)
            lbl.setToolTip("")
        if name not in {"None", "Custom"}:
            img_path = os.path.join(os.path.dirname(__file__), "Hero Images", f"{name.capitalize()}.png")
            if os.path.exists(img_path):
                img_label.set_image(img_path)
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
        self.name_edit.setText(new_name)

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
        self._user_named = bool(cfg.get("army_name"))
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
            self.hero_overrides[idx] = {}
            self._hero_names[idx] = "None"
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
                self.hero_overrides[idx] = overrides
            else:
                hero_name_display = name
                self.custom_heroes[idx] = {k: v for k, v in hero_cfg.items() if k != "skill_overrides"}
                self.hero_overrides[idx] = overrides
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
            self._hero_selected(idx, hero_name_display)
        for idx, combo in enumerate(hero_combos, start=1):
            self._hero_selected(idx, combo.currentText())

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
                heroes_cfg.append(cfg)

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
        self.speed_spin.setSingleStep(0.1)
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
    """Graphics item representing an army with portraits and a health bar."""

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
        self._drag_offset = QtCore.QPointF()
        self._dragging = False
        if self._on_drop is not None:
            self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)

    def boundingRect(self) -> QtCore.QRectF:  # type: ignore[override]
        """Return the bounding rectangle for the icon including the health bar."""

        # The item reserves a small extra margin to accommodate the vertical
        # health bar.  When the bar is drawn on the left we need to shift the
        # rectangle accordingly so the scene knows to paint that area as well.
        extra = 6  # bar width (4px) + 2px spacing
        width = self.main_pix.width() + extra
        height = self.main_pix.height()
        return QtCore.QRectF(-extra, 0, width, height)

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


class SlotItem(QtWidgets.QGraphicsEllipseItem):
    """Clickable marker representing a deployment slot."""

    def __init__(
        self,
        team: str,
        index: int,
        radius: float,
        on_click: Callable[[str, int], None],
    ) -> None:
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.team = team
        self.index = index
        self._on_click = on_click
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
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._on_click(self.team, self.index)
        super().mouseDoubleClickEvent(event)


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
        self._icon_size = int(min(self._cell_w, self._cell_h) * 0.8 * 3 * 0.75)
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
        """Update health bars in response to engine state broadcasts."""
        icon = self._icons.get(name)
        if not icon:
            return
        ctx = self.engine._armies.get(name)
        if not ctx:
            return
        army = ctx.army
        initial = max(1.0, army.unit.initial_count)
        icon.set_health(army.current_troop_count / initial)

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


class SimulationWorker(QtCore.QThread):
    progress_update = QtCore.pyqtSignal(int, int)
    finished_text = QtCore.pyqtSignal(str, object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, setup_data: list[dict], runs: int, num_workers: int) -> None:
        super().__init__()
        self.setup_data = setup_data
        self.runs = runs
        self.num_workers = num_workers
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """Request the simulation to stop."""
        self._cancelled.set()

    def run(self) -> None:
        try:
            armies = create_armies_from_data(self.setup_data)
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            report_builder = ReportBuilder(use_color=False)
            sim = GameSimulator(armies[0], armies[1], report_builder, track_stats=True)
            report_text = sim.simulate_battle()
            rounds = report_builder.get_rounds()
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            def progress_cb(done: int, total: int) -> None:
                self.progress_update.emit(done, total)
                if self._cancelled.is_set():
                    raise RuntimeError("cancelled")

            win_rate = run_additional_simulations(
                self.setup_data,
                runs=self.runs,
                verbose=False,
                progress_callback=progress_cb,
                num_workers=self.num_workers,
            )
            if self._cancelled.is_set():
                raise RuntimeError("cancelled")

            result_text = (
                report_text
                + f"\nWin rate for {armies[0].name}: {win_rate*100:.1f}% over {self.runs} runs.\n"
            )
            self.finished_text.emit(result_text, rounds)
        except RuntimeError as exc:  # pragma: no cover - GUI feedback
            if str(exc) == "cancelled":
                self.finished_text.emit("Simulation cancelled.", [])
            else:
                self.error.emit(str(exc))
        except Exception as exc:  # pragma: no cover - GUI feedback
            self.error.emit(str(exc))


class ArenaBatchWorker(QtCore.QThread):
    progress_update = QtCore.pyqtSignal(int, int)
    finished_dict = QtCore.pyqtSignal(dict)

    def __init__(self, layout_entries: list[dict[str, Any]], runs: int, num_workers: int) -> None:
        super().__init__()
        self.layout_entries = layout_entries
        self.runs = runs
        self.num_workers = num_workers
        self._cancelled = threading.Event()

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
            engine.start_arena_battle(battle_layout)
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
        self.last_run_btn = QtWidgets.QPushButton("Last Run")
        self.swap_btn = QtWidgets.QPushButton("Swap Teams")
        self.refresh_btn = QtWidgets.QPushButton("Refresh Arena")
        self.run_btn = QtWidgets.QPushButton("Run Arena")
        self.run_batch_btn = QtWidgets.QPushButton("Run Batch")
        self.speed_btn = QtWidgets.QPushButton("Speed 1x")
        self.time_label = QtWidgets.QLabel("00:00")
        for btn in (
            self.save_layout_btn,
            self.load_layout_btn,
            self.last_run_btn,
            self.swap_btn,
            self.refresh_btn,
            self.run_btn,
            self.run_batch_btn,
            self.speed_btn,
        ):
            controls.addWidget(btn)
        controls.addWidget(self.time_label)
        controls.addStretch()
        layout.addLayout(controls)

        self._setups_dir = os.path.join(os.path.dirname(__file__), "setups")
        self.saved_armies_file = os.path.join(self._setups_dir, "saved_armies.json")
        self.last_layout_file = os.path.join(self._setups_dir, "_last_arena_layout.json")

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
        self._icon_size = int(min(self._cell_w, self._cell_h) * 0.8 * 3 * 0.75)
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
                item = SlotItem(team, idx, radius, self._slot_clicked)
                item.setPos(x, y)
                self.scene.addItem(item)
                self._slot_items[(team, idx)] = item
                self._slot_army[(team, idx)] = None

        self.refresh_btn.clicked.connect(self._refresh_arena)
        self.save_layout_btn.clicked.connect(self._save_layout)
        self.load_layout_btn.clicked.connect(self._load_layout)
        self.last_run_btn.clicked.connect(self._run_last_layout)
        self.swap_btn.clicked.connect(self._swap_teams)
        self.run_btn.clicked.connect(self._run_arena)
        self.run_batch_btn.clicked.connect(self._run_batch)
        self.speed_btn.clicked.connect(self._toggle_speed)

    # ------------------------------------------------------------------
    def _compute_slot_coords(self) -> dict[str, list[tuple[float, float]]]:
        """Return coordinates for each deployment slot of both teams."""

        default_speed = 50.0
        engage_dist = 2 * default_speed * 2  # 200.0 units between opposing fronts
        to_mid = engage_dist / 2.0  # distance from front line to map centre
        back_offset = default_speed * 3 * 0.7  # 105.0 units between front and back rows

        cx = self.view.sceneRect().width() / 2.0
        cy = self.view.sceneRect().height() / 2.0

        # Vertical offsets for the four columns relative to the centre.
        offsets = [
            -1.5 * engage_dist,
            -0.5 * engage_dist,
            0.5 * engage_dist,
            1.5 * engage_dist,
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
        )
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

    def _collect_layout_data(self) -> list[dict[str, Any]]:
        """Return layout entries for all occupied slots."""

        data: list[dict[str, Any]] = []
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
            data.append(entry)
        return data

    def _save_last_layout(self) -> None:
        """Persist the current layout for quick access later."""

        data = self._collect_layout_data()
        if not data:
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
        if not data:
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

    def _apply_layout(self, layout_data: list[dict[str, Any]]) -> None:
        """Apply a previously saved layout to the arena."""

        try:
            with open(self.saved_armies_file, "r", encoding="utf-8") as fh:
                saved_armies = json.load(fh)
        except (OSError, json.JSONDecodeError):
            # Missing or invalid ``saved_armies`` should not block loading –
            # layouts now embed full army configs so we can continue without it.
            saved_armies = {}

        self._refresh_arena()
        for entry in layout_data:
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
            )
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
        self.engine.start_arena_battle(layout)
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
                engine.start_arena_battle(battle_layout)
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
        worker = ArenaBatchWorker(layout_entries, runs, workers)
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
        """Update health bars in response to engine state broadcasts."""
        icon = self._icons.get(name)
        if not icon:
            return
        ctx = self.engine._armies.get(name)
        if not ctx:
            return
        army = ctx.army
        initial = max(1.0, army.unit.initial_count)
        icon.set_health(army.current_troop_count / initial)

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
            for (slot_team, _), info in self._slot_army.items():
                if not info:
                    continue
                army = info["army"]
                healed = int(round(army.troops_healed_total))
                kills = int(round(sum(army.kills_dealt_history)))
                remaining = int(round(army.current_troop_count))
                initial = int(round(army.unit.initial_count))
                cfg = info.get("config", {})
                heroes = cfg.get("heroes", [])
                if heroes:
                    portrait1 = os.path.join(
                        os.path.dirname(__file__),
                        "Hero Images",
                        f"{heroes[0]['hero_name_or_preset'].capitalize()}.png",
                    )
                    portrait2 = (
                        os.path.join(
                            os.path.dirname(__file__),
                            "Hero Images",
                            f"{heroes[1]['hero_name_or_preset'].capitalize()}.png",
                        )
                        if len(heroes) > 1
                        else ""
                    )
                else:
                    portrait1 = os.path.join(
                        os.path.dirname(__file__),
                        "Icons",
                        f"{cfg.get('unit_type', '').capitalize()}.png",
                    )
                    portrait2 = ""
                summary.append(
                    {
                        "team": info["team"],
                        "name": army.name,
                        "portrait1": portrait1,
                        "portrait2": portrait2,
                        "remaining": remaining,
                        "initial": initial,
                        "healed": healed,
                        "kills": kills,
                    }
                )
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
                item = SlotItem(team, idx, radius, self._slot_clicked)
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
        main_layout = self._init_tabs()
        self._init_status_controls(main_layout)
        self.pdf_layout = load_pdf_layout()

    def open_star_overlay_tuner(self) -> None:
        """Open the star overlay debug dialog."""
        dlg = StarOverlayDebugDialog(self)
        dlg.exec()

    def open_pdf_layout_tool(self) -> None:
        """Open the PDF layout configuration dialog."""
        dlg = PDFLayoutDialog(self)
        if dlg.exec():
            self.pdf_layout = load_pdf_layout()

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
        star_action = dbg_menu.addAction("Star Layout")
        star_action.triggered.connect(self.open_star_overlay_tuner)
        debug_btn.setMenu(dbg_menu)
        debug_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        controls.addWidget(debug_btn)
        controls.addStretch()
        setup_layout.addLayout(controls)

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
        self.arena_fig_summary = QtWidgets.QWidget()
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
        export_pdf_action = QtGui.QAction("Export PDF", self)
        export_pdf_action.triggered.connect(self.export_pdf)
        for act in (
            export_report_action,
            export_fig_action,
            export_summary_action,
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

        # Multi-army tabs
        self.tabs.addTab(self.battlefield_tab, "Battlefield")
        self.tabs.addTab(self.battlefield_report_tab, "Battlefield Reports")
        self.tabs.addTab(self.arena_tab, "Arena")
        self.tabs.addTab(self.arena_report_tab, "Arena Reports")
        self.tabs.addTab(self.arena_figures_tab, "Arena Figures")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        return main_layout

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
            labels = [k.capitalize() for k in results.keys()]
            sizes = list(results.values())
            fig, ax = plt.subplots()
            ax.pie(sizes, labels=labels, autopct="%1.1f%%")
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
        team_layouts: dict[str, QtWidgets.QVBoxLayout] = {
            "red": QtWidgets.QVBoxLayout(),
            "blue": QtWidgets.QVBoxLayout(),
        }
        for layout in team_layouts.values():
            layout.addWidget(HeroStatsHeader())
        for entry in results:
            widget = HeroStatsWidget(
                entry.get("portrait1", ""),
                entry.get("portrait2", ""),
                entry.get("name", ""),
                entry.get("remaining", 0),
                entry.get("initial", entry.get("remaining", 0)),
                entry.get("healed", 0),
                entry.get("kills", 0),
                entry.get("team", "red"),
            )
            team_layouts.get(entry.get("team", ""), team_layouts["red"]).addWidget(widget)

        red_widget = QtWidgets.QWidget()
        red_layout = QtWidgets.QVBoxLayout(red_widget)
        red_layout.addLayout(team_layouts["red"])
        red_layout.addStretch()
        blue_widget = QtWidgets.QWidget()
        blue_layout = QtWidgets.QVBoxLayout(blue_widget)
        blue_layout.addLayout(team_layouts["blue"])
        blue_layout.addStretch()
        self.arena_fig_summary_layout.addWidget(red_widget, 0, 0)
        self.arena_fig_summary_layout.addWidget(blue_widget, 0, 1)
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

        def make_transparent(
            pix: QtGui.QPixmap, bg_color: QtGui.QColor | None = None
        ) -> QtGui.QPixmap:
            fmt_obj = getattr(QtGui.QImage, "Format", None)
            if fmt_obj is not None and hasattr(fmt_obj, "Format_ARGB32"):
                fmt = fmt_obj.Format_ARGB32
            else:
                fmt = QtGui.QImage.Format_ARGB32
            image = pix.toImage().convertToFormat(fmt)
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
        hist_pixmaps: dict[str, QtGui.QPixmap] = {}
        for fname in image_files:
            path = os.path.join(base_hist_dir, fname)
            if os.path.exists(path):
                pm = QtGui.QPixmap(path)
                pm = make_transparent(pm)
                hist_pixmaps[os.path.splitext(fname)[0]] = pm
        if not hist_pixmaps:
            return None, {}

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
            padding = vs_pix.width() // 2
            extra_after_vs = 300
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
            fmt_obj = getattr(QtGui.QImage, "Format", None)
            if fmt_obj is not None and hasattr(fmt_obj, "Format_ARGB32"):
                fmt = fmt_obj.Format_ARGB32
            else:
                fmt = QtGui.QImage.Format_ARGB32
            image = pix.toImage().convertToFormat(fmt)
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

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Summary Image",
            self.last_setup_dir,
            "PNG Files (*.png)"
        )
        if save_path:
            final_pix.save(save_path, "PNG")

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
        runs = self.runs_spin.value()
        workers = self.workers_spin.value()
        self.status.setText("Running simulation...")
        self.progress.setRange(0, runs)
        self.progress.setValue(0)
        self.run_btn.setText("Cancel")
        self.worker = SimulationWorker(setup_data, runs, workers)
        self.worker.progress_update.connect(
            lambda d, t: (self.progress.setMaximum(t), self.progress.setValue(d))
        )
        self.worker.finished_text.connect(self._sim_finished)
        self.worker.error.connect(self._sim_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()
 
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

    def _sim_finished(self, text: str, rounds: list[dict]) -> None:
        self.output_text.setPlainText(text)
        self._populate_round_tree(rounds)
        display_histograms(
            self.hist_scroll,
            self.army1_frame.name_edit.text() or f"Army 1",
            self.army2_frame.name_edit.text() or f"Army 2",
        )
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

