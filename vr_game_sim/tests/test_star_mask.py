import os

import numpy as np
from PIL import Image, ImageQt
from PyQt6 import QtWidgets, QtGui, QtCore

from vr_game_sim.gui_main import StarredImageLabel


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _grey_mask_from_label(label: StarredImageLabel) -> np.ndarray:
    """Return a boolean mask where the pixmap differs from pure white."""

    qimg = label.pixmap().toImage()
    img = ImageQt.fromqimage(qimg).convert("RGBA")
    arr = np.array(img)
    return np.any(arr != [255, 255, 255, 255], axis=2)


def _expected_mask(label: StarredImageLabel, missing: list[int]) -> np.ndarray:
    """Compute expected grey mask using the label's star polygon helper."""

    w, h = label._orig_image.size
    star_width = w / label.MAX_STARS
    star_height = h * (1 - label.STAR_VERTICAL_RATIO)

    qimg = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32)
    qimg.fill(0)
    painter = QtGui.QPainter(qimg)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor(255, 255, 255, 255))
    poly = label._build_star_polygon(int(star_width), int(star_height))
    y_offset = h - star_height
    for idx in missing:
        painter.save()
        painter.translate(int(idx * star_width), int(y_offset))
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

