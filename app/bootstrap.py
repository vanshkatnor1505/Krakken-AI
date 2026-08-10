"""
Application bootstrap for Kraken AI.

Responsible for:

- Initializing core services
- Registering dependencies
- Creating the Groq AI provider
- Creating the AssistantService
- Creating the AssistantBridge
- Creating the Qt application
- Creating the QML engine
- Exposing backend services to QML
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
from core.ai.provider import GroqProvider
from core.bridge.assistant_bridge import AssistantBridge
from core.events.event_bus import event_bus
from core.services.assistant_service import AssistantService
from core.services.container import container
from core.services.logger import log_manager


class ApplicationBootstrap:
    """
    Bootstraps the Kraken AI application.
    """

    def __init__(self) -> None:

        self.app: QGuiApplication | None = None

        self.engine: QQmlApplicationEngine | None = None

        self.window = None

        # Strong references are important because these
        # objects participate in the application lifecycle.

        self.provider: GroqProvider | None = None

        self.assistant_service: AssistantService | None = None

        self.bridge: AssistantBridge | None = None

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def initialize(self) -> None:
        """
        Initialize all backend services.
        """

        # ------------------------------------------------------
        # LOGGER
        # ------------------------------------------------------

        log_manager.setup()

        logger = log_manager.instance

        logger.info(
            "Initializing Kraken AI..."
        )

        # ------------------------------------------------------
        # CORE SERVICES
        # ------------------------------------------------------

        container.register_singleton(
            "config",
            config,
        )

        container.register_singleton(
            "logger",
            logger,
        )

        container.register_singleton(
            "event_bus",
            event_bus,
        )

        logger.success(
            "Core services registered."
        )

        # ------------------------------------------------------
        # GROQ AI PROVIDER
        # ------------------------------------------------------

        logger.info(
            "Initializing Groq AI provider..."
        )

        try:

            self.provider = GroqProvider(
                api_key=config.groq_api_key,
                model=config.groq_model,
                logger=logger,
            )

        except Exception as exc:

            logger.error(
                f"Failed to initialize Groq provider: {exc}"
            )

            raise

        container.register_singleton(
            "ai_provider",
            self.provider,
        )

        logger.success(
            f"Groq provider initialized: "
            f"{config.groq_model}"
        )

        # ------------------------------------------------------
        # ASSISTANT SERVICE
        # ------------------------------------------------------

        if self.provider is None:

            raise RuntimeError(
                "Groq provider was not initialized."
            )

        logger.info(
            "Initializing AssistantService..."
        )

        self.assistant_service = AssistantService(
            event_bus=event_bus,
            provider=self.provider,
            logger=logger,
        )

        container.register_singleton(
            "assistant_service",
            self.assistant_service,
        )

        logger.success(
            "Assistant service initialized."
        )

        # ------------------------------------------------------
        # ASSISTANT BRIDGE
        # ------------------------------------------------------

        logger.info(
            "Initializing AssistantBridge..."
        )

        self.bridge = AssistantBridge(
            event_bus=event_bus,
            logger=logger,
        )

        container.register_singleton(
            "assistant_bridge",
            self.bridge,
        )

        logger.success(
            "Assistant bridge initialized."
        )

        # ------------------------------------------------------
        # COMPLETE
        # ------------------------------------------------------

        logger.success(
            "Core services initialized successfully."
        )

    # ==========================================================
    # RUN APPLICATION
    # ==========================================================

    def run(self) -> int:
        """
        Start the Kraken AI application.
        """

        # ------------------------------------------------------
        # INITIALIZE BACKEND
        # ------------------------------------------------------

        self.initialize()

        logger = log_manager.instance

        # ------------------------------------------------------
        # QT STYLE
        # ------------------------------------------------------

        QQuickStyle.setStyle(
            "Basic"
        )

        # ------------------------------------------------------
        # QT APPLICATION
        # ------------------------------------------------------

        self.app = QGuiApplication(
            sys.argv
        )

        # ------------------------------------------------------
        # QML ENGINE
        # ------------------------------------------------------

        self.engine = QQmlApplicationEngine()

        # ------------------------------------------------------
        # PROJECT PATHS
        # ------------------------------------------------------

        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        qml_root = (
            project_root
            / "ui"
            / "qml"
        ).resolve()

        logger.info(
            f"QML root: {qml_root}"
        )

        # ------------------------------------------------------
        # QML IMPORT PATH
        # ------------------------------------------------------

        self.engine.addImportPath(
            str(qml_root)
        )

        # ------------------------------------------------------
        # VALIDATE QML ROOT
        # ------------------------------------------------------

        if not qml_root.exists():

            logger.error(
                f"QML directory not found: {qml_root}"
            )

            raise FileNotFoundError(
                f"QML directory not found: {qml_root}"
            )

        # ------------------------------------------------------
        # VALIDATE BRIDGE
        # ------------------------------------------------------

        if self.bridge is None:

            raise RuntimeError(
                "AssistantBridge was not initialized."
            )

        # ------------------------------------------------------
        # EXPOSE BRIDGE TO QML
        # ------------------------------------------------------

        self.engine.rootContext().setContextProperty(
            "assistantBridge",
            self.bridge,
        )

        logger.success(
            "Assistant bridge exposed to QML."
        )

        # ------------------------------------------------------
        # MAIN QML
        # ------------------------------------------------------

        qml_file = (
            qml_root
            / "Main.qml"
        )

        logger.info(
            f"Loading QML: {qml_file}"
        )

        if not qml_file.exists():

            logger.error(
                f"Main.qml not found: {qml_file}"
            )

            raise FileNotFoundError(
                f"Main.qml not found: {qml_file}"
            )

        # ------------------------------------------------------
        # LOAD QML
        # ------------------------------------------------------

        self.engine.load(
            QUrl.fromLocalFile(
                str(qml_file)
            )
        )

        # ------------------------------------------------------
        # VERIFY QML
        # ------------------------------------------------------

        if not self.engine.rootObjects():

            logger.error(
                "Failed to load Main.qml"
            )

            raise RuntimeError(
                "Failed to load Main.qml"
            )

        self.window = (
            self.engine.rootObjects()[0]
        )

        # ------------------------------------------------------
        # READY
        # ------------------------------------------------------

        logger.success(
            "UI loaded successfully."
        )

        logger.success(
            "Krakken AI is running."
        )

        # ------------------------------------------------------
        # QT EVENT LOOP
        # ------------------------------------------------------

        return self.app.exec()