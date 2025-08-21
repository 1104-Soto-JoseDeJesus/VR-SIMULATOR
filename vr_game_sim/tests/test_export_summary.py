import os
from PyQt6 import QtWidgets

from vr_game_sim.gui_main import MainWindow


def test_export_summary_image(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    window = MainWindow()

    # Avoid interactive dialogs
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        classmethod(lambda *args, **kwargs: (str(tmp_path / "summary.png"), None)),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        classmethod(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        classmethod(lambda *args, **kwargs: None),
    )

    window.export_summary_image()
    assert (tmp_path / "summary.png").exists()
