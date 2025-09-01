from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


class HeroStatsWidget(QtWidgets.QWidget):
    """Display summary statistics for a hero in the arena."""

    def __init__(
        self,
        portrait_path: str,
        name: str,
        remaining: int,
        healed: int,
        kills: int,
        team_color: str,
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

        # Stats labels
        name_label = QtWidgets.QLabel(name)
        remaining_label = QtWidgets.QLabel(str(remaining))
        healed_label = QtWidgets.QLabel(str(healed))
        kills_label = QtWidgets.QLabel(str(kills))

        for col, widget in enumerate(
            [name_label, remaining_label, healed_label, kills_label], start=1
        ):
            widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            widget.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            layout.addWidget(widget, 0, col)
            layout.setColumnStretch(col, 1)

        layout.setColumnStretch(1, 2)  # make name column wider
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        if team_color:
            # outline widget with team color
            self.setStyleSheet(f"border: 1px solid {team_color};")
