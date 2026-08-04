"""
Application bootstrap for Kraken AI.

Responsible for:
- Initializing core services
- Registering dependencies
- Starting the Qt application
- Loading the QML interface
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from app.config import config
from core.events.event_bus import event_bus
from core.services.container import container
from core.services.logger import log_manager


class ApplicationBootstrap:
    """Bootstraps the Kraken AI application."""

    def __init__(self) -> None:
        self.app: QGuiApplication | None = None
        self.engine: QQmlApplicationEngine | None = None
        self.window = None

    def initialize(self) -> None:
        """Initialize all backend services."""

        log_manager.setup()
        logger = log_manager.instance

        logger.info("Initializing Kraken AI...")

        container.register_singleton("config", config)
        container.register_singleton("logger", logger)
        container.register_singleton("event_bus", event_bus)

        logger.success("Core services initialized.")

    def run(self) -> int:
        """Start the application."""

        self.initialize()

        logger = log_manager.instance

        QQuickStyle.setStyle("Basic")

        self.app = QGuiApplication(sys.argv)

        self.engine = QQmlApplicationEngine()

        # -------------------------------------------------
        # Register QML module import path
        # -------------------------------------------------

        qml_root = Path("ui/qml").resolve()

        self.engine.addImportPath(str(qml_root))

        # -------------------------------------------------
        # Future backend exposure
        # -------------------------------------------------

        # self.engine.rootContext().setContextProperty(
        #     "backend",
        #     backend_instance,
        # )

        # -------------------------------------------------
        # Load Main.qml
        # -------------------------------------------------

        qml_file = qml_root / "Main.qml"

        logger.info(f"Loading QML: {qml_file}")

        self.engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self.engine.rootObjects():
            logger.error("Failed to load Main.qml")
            raise RuntimeError("Failed to load Main.qml")

        self.window = self.engine.rootObjects()[0]

        logger.success("UI loaded successfully.")

        return self.app.exec()