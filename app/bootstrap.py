"""
Application bootstrap for Krakken AI.

Responsible for:

- Initializing core services
- Registering dependencies
- Creating the Groq AI provider
- Creating the Kokoro TTS provider
- Creating the AudioPlayer
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
from core.voice.audio_player import AudioPlayer
from core.voice.providers.kokoro_provider import KokoroProvider


class ApplicationBootstrap:
    """
    Bootstraps the Krakken AI application.
    """

    def __init__(self) -> None:

        self.app: QGuiApplication | None = None
        self.engine: QQmlApplicationEngine | None = None
        self.window = None

        # Strong references are important because these objects
        # participate in the application lifecycle.

        self.provider: GroqProvider | None = None
        self.tts_provider: KokoroProvider | None = None
        self.audio_player: AudioPlayer | None = None
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
        # Logger
        # ------------------------------------------------------

        log_manager.setup()

        logger = log_manager.instance

        logger.info(
            "Initializing Krakken AI..."
        )

        # ------------------------------------------------------
        # Core services
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

        # ======================================================
        # GROQ AI PROVIDER
        # ======================================================

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

        # ======================================================
        # KOKORO TTS
        # ======================================================

        logger.info(
            "Initializing Kokoro TTS provider..."
        )

        try:

            self.tts_provider = KokoroProvider(
                voice="af_heart",
                speed=1.0,
                logger=logger,
            )

            self.tts_provider.initialize()

        except Exception as exc:

            logger.error(
                f"Failed to initialize Kokoro TTS: {exc}"
            )

            raise

        container.register_singleton(
            "tts_provider",
            self.tts_provider,
        )

        logger.success(
            "Kokoro TTS provider initialized."
        )

        # ======================================================
        # AUDIO PLAYER
        # ======================================================

        logger.info(
            "Initializing AudioPlayer..."
        )

        try:

            self.audio_player = AudioPlayer(
                logger=logger,
            )

        except Exception as exc:

            logger.error(
                f"Failed to initialize AudioPlayer: {exc}"
            )

            raise

        container.register_singleton(
            "audio_player",
            self.audio_player,
        )

        logger.success(
            "AudioPlayer initialized."
        )

        # ======================================================
        # ASSISTANT SERVICE
        # ======================================================

        logger.info(
            "Initializing AssistantService..."
        )

        if self.provider is None:
            raise RuntimeError(
                "Groq provider was not initialized."
            )

        if self.tts_provider is None:
            raise RuntimeError(
                "Kokoro TTS provider was not initialized."
            )

        if self.audio_player is None:
            raise RuntimeError(
                "AudioPlayer was not initialized."
            )

        self.assistant_service = AssistantService(
            event_bus=event_bus,
            provider=self.provider,
            logger=logger,
            tts_provider=self.tts_provider,
            audio_player=self.audio_player,
        )

        container.register_singleton(
            "assistant_service",
            self.assistant_service,
        )

        logger.success(
            "Assistant service initialized."
        )

        # ======================================================
        # ASSISTANT BRIDGE
        # ======================================================

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

        # ======================================================
        # COMPLETE
        # ======================================================

        logger.success(
            "Core services initialized successfully."
        )

    # ==========================================================
    # RUN APPLICATION
    # ==========================================================

    def run(self) -> int:
        """
        Start the Krakken AI application.
        """

        # ------------------------------------------------------
        # Initialize backend
        # ------------------------------------------------------

        self.initialize()

        logger = log_manager.instance

        # ------------------------------------------------------
        # Qt style
        # ------------------------------------------------------

        QQuickStyle.setStyle(
            "Basic"
        )

        # ------------------------------------------------------
        # Qt application
        # ------------------------------------------------------

        self.app = QGuiApplication(
            sys.argv
        )

        # ------------------------------------------------------
        # QML engine
        # ------------------------------------------------------

        self.engine = QQmlApplicationEngine()

        # ------------------------------------------------------
        # Project paths
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
        # QML import path
        # ------------------------------------------------------

        self.engine.addImportPath(
            str(qml_root)
        )

        # ------------------------------------------------------
        # Validate QML root
        # ------------------------------------------------------

        if not qml_root.exists():

            logger.error(
                f"QML directory not found: {qml_root}"
            )

            raise FileNotFoundError(
                f"QML directory not found: {qml_root}"
            )

        # ------------------------------------------------------
        # Validate bridge
        # ------------------------------------------------------

        if self.bridge is None:

            raise RuntimeError(
                "AssistantBridge was not initialized."
            )

        # ------------------------------------------------------
        # Expose bridge to QML
        #
        # IMPORTANT:
        #
        # We intentionally use "krakkenBridge"
        # instead of "assistantBridge".
        #
        # ChatView already has a property named
        # assistantBridge, so using the same name
        # caused QML scope resolution problems.
        # ------------------------------------------------------

        self.engine.rootContext().setContextProperty(
            "krakkenBridge",
            self.bridge,
        )

        logger.success(
            "Assistant bridge exposed to QML as 'krakkenBridge'."
        )

        # ------------------------------------------------------
        # Main QML
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
        # Load QML
        # ------------------------------------------------------

        self.engine.load(
            QUrl.fromLocalFile(
                str(qml_file)
            )
        )

        # ------------------------------------------------------
        # Verify QML
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
        # Application ready
        # ------------------------------------------------------

        logger.success(
            "UI loaded successfully."
        )

        logger.success(
            "Krakken AI is running."
        )

        # ------------------------------------------------------
        # Qt event loop
        # ------------------------------------------------------

        return self.app.exec()