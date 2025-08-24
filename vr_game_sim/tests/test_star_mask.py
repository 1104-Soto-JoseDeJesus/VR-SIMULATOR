import os
import numpy as np
from PIL import Image, ImageQt
from PyQt6 import QtWidgets, QtGui, QtCore

from vr_game_sim.gui_main import StarredImageLabel


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _grey_mask_from_label(label: StarredImageLabel) -> np.ndarray:
    """Return a mask of greyed pixels by diffing against a full-star baseline."""

    # Grab image with grey overlay applied
    qimg = label.pixmap().toImage()
    with_overlay = ImageQt.fromqimage(qimg).convert("RGBA")
    with_overlay = with_overlay.resize(label._orig_image.size, Image.NEAREST)

    # Render baseline with all stars visible
    current = label.star_count
    label.star_count = label.max_stars
    label._update_pixmap()
    base_qimg = label.pixmap().toImage()
    baseline = ImageQt.fromqimage(base_qimg).convert("RGBA")
    baseline = baseline.resize(label._orig_image.size, Image.NEAREST)
    # Restore original star count
    label.star_count = current
    label._update_pixmap()

    arr = np.array(with_overlay)
    base_arr = np.array(baseline)
    return np.any(arr != base_arr, axis=2)


def _expected_mask(label: StarredImageLabel, missing: list[int]) -> np.ndarray:
    """Compute expected grey mask using the label's star polygon helper."""

    w, h = label._orig_image.size
    max_stars = label.max_stars
    cell_width = w * (1 - 2 * label.star_side_margin_ratio) / max_stars
    base_height = h * (1 - label.star_vertical_ratio)
    x_offset = w * label.star_side_margin_ratio

    qimg = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32)
    qimg.fill(0)
    painter = QtGui.QPainter(qimg)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor(255, 255, 255, 255))
    for idx in missing:
        painter.save()
        v_off = 0.0
        h_off = 0.0
        scale = 1.0
        if label._is_hero_image:
            if idx < len(label.hero_star_v_offsets):
                v_off = label.hero_star_v_offsets[idx]
            if idx < len(label.hero_star_h_offsets):
                h_off = label.hero_star_h_offsets[idx]
            if idx < len(label.hero_star_size_factors):
                scale = label.hero_star_size_factors[idx]
        elif label._is_plugin_image:
            if idx < len(label.plugin_star_v_offsets):
                v_off = label.plugin_star_v_offsets[idx]
            if idx < len(label.plugin_star_h_offsets):
                h_off = label.plugin_star_h_offsets[idx]
            if idx < len(label.plugin_star_size_factors):
                scale = label.plugin_star_size_factors[idx]

        star_w = cell_width * scale
        star_h = base_height * scale
        poly = label._build_star_polygon(int(star_w), int(star_h))
        assert len(poly) == 8
        y_offset = h - star_h + v_off * star_h
        x_pos = x_offset + idx * cell_width + (cell_width - star_w) / 2 + h_off * star_w
        painter.translate(int(x_pos), int(y_offset))
        painter.drawPolygon(poly)
        painter.restore()
    painter.end()

    mask_img = ImageQt.fromqimage(qimg)
    mask_arr = np.array(mask_img)
    return mask_arr[:, :, 3] > 0


def test_star_mask_application():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    label = StarredImageLabel()
    w, h = 60, 40
    label.resize(w, h)
    label._orig_image = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    label._is_hero_image = False

    label.star_count = 5
    label._update_pixmap()
    mask1 = _grey_mask_from_label(label)
    expected1 = _expected_mask(label, [5])
    assert not np.any(mask1 & ~expected1)
    assert mask1.sum() > 0

    label.star_count = 3
    label._update_pixmap()
    mask2 = _grey_mask_from_label(label)
    expected2 = _expected_mask(label, [3, 4, 5])
    assert not np.any(mask2 & ~expected2)
    assert mask2.sum() > mask1.sum()


def test_hero_star_alignment():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    label = StarredImageLabel()
    hero_path = os.path.join(os.path.dirname(__file__), "..", "Hero Images", "Laird.png")
    label.set_image(os.path.normpath(hero_path))
    w, h = label._orig_image.size
    label.resize(w, h)

    label.set_star_count(4)
    mask = _grey_mask_from_label(label)
    expected = _expected_mask(label, [4, 5])
    assert not np.any(mask & ~expected)
    assert mask.sum() > 0


def test_plugin_star_alignment():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    label = StarredImageLabel()
    plugin_path = os.path.join(
        os.path.dirname(__file__), "..", "Plugin Skill Images", "Awakening.png"
    )
    label.set_image(os.path.normpath(plugin_path))
    w, h = label._orig_image.size
    label.resize(w, h)

    assert label.star_vertical_ratio == 0.83

    label.set_star_count(4)
    mask = _grey_mask_from_label(label)
    expected = _expected_mask(label, [4, 5])
    assert not np.any(mask & ~expected)
    assert mask.sum() > 0


def test_horizontal_offsets():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    label = StarredImageLabel()
    w, h = 60, 40
    label.resize(w, h)
    label._orig_image = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    label._is_hero_image = True

    label.set_layout(
        6,
        label.DEFAULT_STAR_VERTICAL_RATIO,
        0.0,
        offsets=label.hero_star_v_offsets,
        h_offsets=[0.5, 0, 0, 0, 0, 0],
    )
    label.star_count = 5
    label._update_pixmap()
    mask = _grey_mask_from_label(label)
    expected = _expected_mask(label, [5])
    assert not np.any(mask & ~expected)
    assert mask.sum() > 0


def test_plugin_offsets():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    label = StarredImageLabel()
    w, h = 60, 40
    label.resize(w, h)
    label._orig_image = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    label._is_plugin_image = True

    label.set_layout(
        6,
        label.DEFAULT_STAR_VERTICAL_RATIO,
        0.0,
        offsets=[0, 0, 0, 0, 0, 0.5],
        h_offsets=[0, 0, 0, 0, 0, 0.5],
    )
    label.star_count = 5
    label._update_pixmap()
    mask = _grey_mask_from_label(label)
    expected = _expected_mask(label, [5])
    assert not np.any(mask & ~expected)
    assert mask.sum() > 0

