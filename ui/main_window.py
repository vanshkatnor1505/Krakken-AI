"""
Main application window for Kraken AI.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Krakken AI")
        self.resize(1400, 900)
        self.setMinimumSize(1100, 700)

        label = QLabel("🚀 Kraken AI Version 2", self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setCentralWidget(label)