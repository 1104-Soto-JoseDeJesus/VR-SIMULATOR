from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


class HeroStatsWidget(QtWidgets.QWidget):
    """Display summary statistics for a hero in the arena."""

    def __init__(
        self,
        portrait_path: str,
        name: str,
        remaining: int,
        initial: int,
        healed: int,
        kills: int,
        team_color: str,
        highlight: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Portrait
        img_label = QtWidgets.QLabel()
        img_label.setFixedSize(64, 64)
        pix = QtGui.QPixmap(portrait_path)
        if pix.isNull():
            img_label.setText("No\nImage")
            img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            img_label.setStyleSheet("background-color: #444; color: white;")
        else:
            pix = pix.scaled(
                img_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(pix)
        layout.addWidget(img_label, 0, 0)

        # Stats labels / bars
        name_label = QtWidgets.QLabel(name)
        healed_label = QtWidgets.QLabel(str(healed))
        kills_label = QtWidgets.QLabel(str(kills))

        remaining_bar = QtWidgets.QProgressBar()
        remaining_bar.setRange(0, max(1, initial))
        remaining_bar.setValue(max(0, remaining))
        remaining_bar.setFormat(f"{remaining}/{initial}")
        remaining_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        widgets = [name_label, remaining_bar, healed_label, kills_label]
        for col, widget in enumerate(widgets, start=1):
            widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            widget.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            layout.addWidget(widget, 0, col)
            layout.setColumnStretch(col, 1)

        layout.setColumnStretch(1, 2)  # make name column wider
        layout.setColumnStretch(2, 3)  # wider for progress bar
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        # Apply team-based styling
        if team_color:
            if team_color.lower() == "red":
                base_bg = "#550000"
            elif team_color.lower() == "blue":
                base_bg = "#000055"
            else:
                base_bg = "#333"
            style = (
                f"background-color: {base_bg};"
                "color: white; font-weight: bold;"
                f"border: 1px solid {team_color};"
            )
            if highlight:
                style += "border: 3px solid gold;"
            self.setStyleSheet(style)
            remaining_bar.setStyleSheet(
                "QProgressBar {"
                "border: 1px solid #333;"
                "background-color: #222;"
                "text-align: center;"
                "color: white;"
                "}"
                f"QProgressBar::chunk {{background-color: {team_color};}}"
            )

