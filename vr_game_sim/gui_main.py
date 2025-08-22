"""PyQt6 based GUI for configuring and running battles."""

from __future__ import annotations

import os
from typing import Any
import threading

from PyQt6 import QtCore, QtGui, QtWidgets
import shutil
from PIL import Image, ImageQt
import numpy as np

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder
from vr_game_sim.main import (
    create_armies_from_data,
    run_additional_simulations,
    save_setup_to_file,
    load_setup_from_file,
)
from vr_game_sim.gui.hero_edit_dialog import HeroEditDialog
from vr_game_sim.gui.army_frame import ArmyFrame


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


class FigureExportWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, image_files: list[str], base_dir: str, dest_dir: str) -> None:
        super().__init__()
        self.image_files = image_files
        self.base_dir = base_dir
        self.dest_dir = dest_dir

    def run(self) -> None:
        try:
            for fname in self.image_files:
                src = os.path.join(self.base_dir, fname)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(self.dest_dir, fname))
            self.finished.emit(self.dest_dir)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self.error.emit(str(exc))


class SummaryImageWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        p1_img: QtGui.QImage,
        p2_img: QtGui.QImage,
        vs_img: QtGui.QImage | None,
        hist_paths: list[str],
        save_path: str,
    ) -> None:
        super().__init__()
        self.p1_img = p1_img
        self.p2_img = p2_img
        self.vs_img = vs_img
        self.hist_paths = hist_paths
        self.save_path = save_path

    @staticmethod
    def _make_transparent(image: QtGui.QImage, bg_color: QtGui.QColor | None = None) -> QtGui.QImage:
        fmt_obj = getattr(QtGui.QImage, "Format", None)
        if fmt_obj is not None and hasattr(fmt_obj, "Format_ARGB32"):
            fmt = fmt_obj.Format_ARGB32
        else:
            fmt = QtGui.QImage.Format_ARGB32
        image = image.convertToFormat(fmt)
        ptr = image.bits()
        ptr.setsize(image.width() * image.height() * 4)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(image.height(), image.width(), 4)
        if bg_color is None:
            bg = arr[0, 0, :3].copy()
        else:
            bg = np.array([bg_color.red(), bg_color.green(), bg_color.blue()], dtype=np.uint8)
        rgb = arr[:, :, :3].astype(np.int16)
        diff = np.abs(rgb - bg.astype(np.int16))
        mask = (diff <= 2).all(axis=-1)
        arr[mask, 3] = 0
        return QtGui.QImage(image)

    def run(self) -> None:
        try:
            hist_images: list[QtGui.QImage] = []
            for path in self.hist_paths:
                if os.path.exists(path):
                    img = QtGui.QImage(path)
                    if not img.isNull():
                        hist_images.append(self._make_transparent(img))
            if not hist_images:
                raise RuntimeError("No histogram images found.")

            p1 = self._make_transparent(self.p1_img)
            p2 = self._make_transparent(self.p2_img)
            preview_parts = [p1]
            if self.vs_img is not None and not self.vs_img.isNull():
                vs = self._make_transparent(self.vs_img)
                preview_parts.extend([vs, p2])
            else:
                preview_parts.append(p2)

            if len(preview_parts) == 3:
                padding = preview_parts[1].width() // 2
                extra_after_vs = 300
                left_space = preview_parts[0].width() + padding
                right_space = preview_parts[2].width() + padding + extra_after_vs
                half_width = max(left_space, right_space)
                preview_width = preview_parts[1].width() + 2 * half_width
                preview_height = max(img.height() for img in preview_parts)
                preview_img = QtGui.QImage(preview_width, preview_height, QtGui.QImage.Format_ARGB32)
                preview_img.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(preview_img)
                vs_x = (preview_width - preview_parts[1].width()) // 2
                vs_y = (preview_height - preview_parts[1].height()) // 2
                painter.drawImage(vs_x, vs_y, preview_parts[1])
                left_x = vs_x - padding - preview_parts[0].width()
                y = (preview_height - preview_parts[0].height()) // 2
                painter.drawImage(left_x, y, preview_parts[0])
                right_x = vs_x + preview_parts[1].width() + padding + extra_after_vs
                y = (preview_height - preview_parts[2].height()) // 2
                painter.drawImage(right_x, y, preview_parts[2])
                painter.end()
            else:
                padding = 30
                preview_width = preview_parts[0].width() + preview_parts[1].width() + padding
                preview_height = max(preview_parts[0].height(), preview_parts[1].height())
                preview_img = QtGui.QImage(preview_width, preview_height, QtGui.QImage.Format_ARGB32)
                preview_img.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(preview_img)
                x = 0
                for idx, part in enumerate(preview_parts):
                    y = (preview_height - part.height()) // 2
                    painter.drawImage(x, y, part)
                    x += part.width()
                    if idx != len(preview_parts) - 1:
                        x += padding
                painter.end()

            final_width = max(preview_img.width(), *(img.width() for img in hist_images))
            final_height = preview_img.height() + sum(img.height() for img in hist_images)
            final_img = QtGui.QImage(final_width, final_height, QtGui.QImage.Format_ARGB32)
            painter = QtGui.QPainter(final_img)
            gradient = QtGui.QLinearGradient(0, 0, 0, final_height)
            gradient.setColorAt(0, QtGui.QColor("#4a4a4a"))
            gradient.setColorAt(1, QtGui.QColor("#1e1e1e"))
            painter.fillRect(QtCore.QRect(0, 0, final_width, final_height), gradient)

            x = (final_width - preview_img.width()) // 2
            painter.drawImage(x, 0, preview_img)
            y = preview_img.height()
            for img in hist_images:
                x = (final_width - img.width()) // 2
                painter.drawImage(x, y, img)
                y += img.height()

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

            label_font = QtGui.QFont("Times New Roman", 80, bold_weight)
            painter.setFont(label_font)
            fm = painter.fontMetrics()
            label = "OMNI"
            x = final_width - fm.horizontalAdvance(label) - margin
            y = final_height - fm.descent() - margin
            painter.drawText(x, y, label)
            painter.end()

            final_img.save(self.save_path, "PNG")
            self.finished.emit(self.save_path)
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

        self.export_btn = QtWidgets.QPushButton("Export Figures")
        self.export_btn.clicked.connect(self.export_figures)
        btn_layout.addWidget(self.export_btn)

        self.summary_btn = QtWidgets.QPushButton("Export Summary Image")
        self.summary_btn.clicked.connect(self.export_summary_image)
        btn_layout.addWidget(self.summary_btn)

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
            self.status.setText("Exporting figures...")
            self.export_btn.setEnabled(False)
            worker = FigureExportWorker(image_files, base_hist_dir, dest_dir)
            worker.finished.connect(self._figures_exported)
            worker.error.connect(self._export_error)
            worker.finished.connect(worker.deleteLater)
            self._current_worker = worker
            worker.start()

    def export_summary_image(self) -> None:
        image_files = [
            "own_remaining_troops.png",
            "enemy_remaining_troops.png",
            "rounds_to_battle_end.png",
            "victory_distribution.png",
        ]
        base_hist_dir = os.path.join(os.path.dirname(__file__), "histograms")
        hist_paths = [
            os.path.join(base_hist_dir, f)
            for f in image_files
            if os.path.exists(os.path.join(base_hist_dir, f))
        ]
        if not hist_paths:
            QtWidgets.QMessageBox.warning(
                self, "No Figures", "No histogram images found. Run a simulation first."
            )
            return
        scale = 5
        p1 = self.army1_frame.preview_widget.grab().toImage().scaled(
            self.army1_frame.preview_widget.width() * scale,
            self.army1_frame.preview_widget.height() * scale,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        p2 = self.army2_frame.preview_widget.grab().toImage().scaled(
            self.army2_frame.preview_widget.width() * scale,
            self.army2_frame.preview_widget.height() * scale,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        vs_pix = self.vs_label.pixmap()
        vs_img = (
            vs_pix.toImage().scaled(
                vs_pix.width() * scale,
                vs_pix.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            if vs_pix and not vs_pix.isNull()
            else None
        )
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Summary Image", self.last_setup_dir, "PNG Files (*.png)"
        )
        if save_path:
            self.status.setText("Exporting summary...")
            self.summary_btn.setEnabled(False)
            worker = SummaryImageWorker(p1, p2, vs_img, hist_paths, save_path)
            worker.finished.connect(self._summary_exported)
            worker.error.connect(self._export_error)
            worker.finished.connect(worker.deleteLater)
            self._current_worker = worker
            worker.start()

    def _figures_exported(self, dest: str) -> None:
        QtWidgets.QMessageBox.information(self, "Export Complete", f"Figures exported to {dest}")
        self.status.setText("Ready")
        self.export_btn.setEnabled(True)

    def _summary_exported(self, path: str) -> None:
        QtWidgets.QMessageBox.information(self, "Export Complete", f"Summary image saved to {path}")
        self.status.setText("Ready")
        self.summary_btn.setEnabled(True)

    def _export_error(self, msg: str) -> None:  # pragma: no cover - GUI feedback
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.status.setText("Ready")
        self.export_btn.setEnabled(True)
        self.summary_btn.setEnabled(True)
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

