import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from PIL import Image
from vr_game_sim import gui_main
from PyQt6 import QtWidgets


def _create_img(path):
    Image.new("RGBA", (10, 10), (255, 255, 255, 255)).save(path)


def test_save_layout_propagates(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    hero_dir = tmp_path / "Hero Images"
    plugin_dir = tmp_path / "Plugin Skill Images"
    hero_dir.mkdir()
    plugin_dir.mkdir()
    _create_img(hero_dir / "h1.png")
    _create_img(hero_dir / "h2.png")
    _create_img(plugin_dir / "p1.png")
    _create_img(plugin_dir / "p2.png")

    original_file = gui_main.__file__
    gui_main.__file__ = str(tmp_path / "dummy.py")
    try:
        dialog = gui_main.StarOverlayDebugDialog()
        # Hero layout save
        h1_path = hero_dir / "h1.png"
        dialog.preview.set_image(str(h1_path))
        dialog.preview.set_layout(
            5,
            0.9,
            0.1,
            offsets=[0.1] * 6,
            h_offsets=[0.2] * 6,
            sizes=[1.1] * 6,
        )
        dialog._save_layout()
        # Expect json for both hero images
        for name in ["h1", "h2"]:
            meta = json.load(open(hero_dir / f"{name}.json"))
            assert meta["star_vertical_ratio"] == 0.9
            assert meta["star_side_margin_ratio"] == 0.1
            assert meta["v_offsets"][0] == 0.1
            assert meta["h_offsets"][0] == 0.2
            assert meta["size_factors"][0] == 1.1
        # Loading second hero should use saved layout
        label = gui_main.StarredImageLabel()
        label.set_image(str(hero_dir / "h2.png"))
        assert label.hero_star_v_offsets[0] == 0.1
        assert label.hero_star_h_offsets[0] == 0.2
        assert label.hero_star_size_factors[0] == 1.1

        # Plugin layout save
        p1_path = plugin_dir / "p1.png"
        dialog.preview.set_image(str(p1_path))
        dialog.preview.set_layout(
            6,
            0.95,
            0.0,
            offsets=[0.3] * 6,
            h_offsets=[0.0] * 6,
            sizes=[1.0] * 6,
        )
        dialog._save_layout()
        for name in ["p1", "p2"]:
            meta = json.load(open(plugin_dir / f"{name}.json"))
            assert meta["star_vertical_ratio"] == 0.95
            assert meta["v_offsets"][0] == 0.3
        # Loading second plugin uses saved layout
        label2 = gui_main.StarredImageLabel()
        label2.set_image(str(plugin_dir / "p2.png"))
        assert label2.plugin_star_v_offsets[0] == 0.3
    finally:
        gui_main.__file__ = original_file
