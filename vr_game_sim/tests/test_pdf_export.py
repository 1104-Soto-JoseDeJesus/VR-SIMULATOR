import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import QtWidgets, QtGui, QtCore
from vr_game_sim import gui_main


def test_export_pdf_writes_valid_file(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    main = gui_main.MainWindow()
    main.pdf_layout = [{"items": [{"type": "dummy", "x": 5, "y": 5}]}]
    pix = QtGui.QPixmap(10, 10)
    pix.fill(QtCore.Qt.GlobalColor.white)
    main.get_pdf_item_pixmap = lambda t: pix
    original_get = QtWidgets.QFileDialog.getSaveFileName
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(
        lambda *args, **kwargs: (str(tmp_path / "out.pdf"), "")
    )
    try:
        main.export_pdf()
    finally:
        QtWidgets.QFileDialog.getSaveFileName = original_get
    data = (tmp_path / "out.pdf").read_bytes()
    assert data.startswith(b"%PDF")
    assert b"%%EOF" in data[-20:]
