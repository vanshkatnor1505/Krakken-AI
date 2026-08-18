"""
Application bootstrap for Krakken AI.

Responsible for:

- Initializing core services
- Registering dependencies
- Creating the Groq AI provider
- Creating the Tool Registry
- Creating the Tool Manager
- Registering application tools
- Creating the Kokoro TTS provider
- Creating the AudioPlayer
- Creating the AssistantService
- Creating the AssistantBridge
- Creating the Qt application
- Creating the QML engine
- Exposing backend services to QML
- Loading the QML interface

Architecture:

    ApplicationBootstrap
            ↓
        ToolRegistry
            ↓
        ToolManager
            ↓
     AssistantService
            ↓
       GroqProvider
            ↓
      AI tool calling
            ↓
     ToolManager
            ↓
    Realtime Tools
            ↓
        Internet
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.tools.builtin.open_app_tool import OpenAppTool
from core.tools.builtin.open_tool import OpenTool

# Realtime internet tools
from core.tools.builtin.web_search_tool import WebSearchTool
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from app.config import config

# ============================================================
# AI
# ============================================================
from core.ai.provider import GroqProvider

# ============================================================
# BRIDGE
# ============================================================
from core.bridge.assistant_bridge import AssistantBridge

# ============================================================
# EVENTS
# ============================================================
from core.events.event_bus import event_bus

# ============================================================
# SERVICES
# ============================================================
from core.services.assistant_service import AssistantService
from core.services.container import container
from core.services.logger import log_manager

# ============================================================
# TOOLS
# ============================================================
from core.tools.registry import ToolRegistry
from core.tools.tool_manager import ToolManager

# ============================================================
# VOICE
# ============================================================
from core.voice.audio_player import AudioPlayer
from core.voice.providers.kokoro_provider import KokoroProvider
from core.voice.voice_input_service import VoiceInputService

# ============================================================
# APPLICATION BOOTSTRAP
# ============================================================


class ApplicationBootstrap:
    """
    Bootstraps the complete Krakken AI application.

    The bootstrap owns application-level dependency wiring.

    It does NOT contain tool implementation logic.

    Tool implementation belongs inside individual Tool classes.
    """

    def __init__(self) -> None:

        # ------------------------------------------------------
        # Qt
        # ------------------------------------------------------

        self.app: QGuiApplication | None = None

        self.engine: QQmlApplicationEngine | None = None

        self.window = None

        # ------------------------------------------------------
        # AI
        # ------------------------------------------------------

        self.provider: GroqProvider | None = None

        # ------------------------------------------------------
        # Voice
        # ------------------------------------------------------

        self.tts_provider: KokoroProvider | None = None

        self.audio_player: AudioPlayer | None = None

        self.voice_input_service: VoiceInputService | None = None

        # ------------------------------------------------------
        # Tools
        # ------------------------------------------------------

        self.tool_registry: ToolRegistry | None = None

        self.tool_manager: ToolManager | None = None

        # ------------------------------------------------------
        # Services
        # ------------------------------------------------------

        self.assistant_service: AssistantService | None = None

        # ------------------------------------------------------
        # Bridge
        # ------------------------------------------------------

        self.bridge: AssistantBridge | None = None

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def initialize(self) -> None:
        """
        Initialize all backend services.

        Initialization order:

            Logger
              ↓
            Core services
              ↓
            Groq
              ↓
            ToolRegistry
              ↓
            ToolManager
              ↓
            Application Tools
              ↓
            Kokoro
              ↓
            AudioPlayer
              ↓
            AssistantService
              ↓
            AssistantBridge
        """

        # ======================================================
        # LOGGER
        # ======================================================

        log_manager.setup()

        logger = log_manager.instance

        logger.info(
            "Initializing Krakken AI..."
        )

        # ======================================================
        # CORE SERVICES
        # ======================================================

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
        # TOOL REGISTRY
        # ======================================================

        logger.info(
            "Initializing ToolRegistry..."
        )

        try:

            self.tool_registry = ToolRegistry()

        except Exception as exc:

            logger.error(
                f"Failed to initialize ToolRegistry: {exc}"
            )

            raise

        container.register_singleton(
            "tool_registry",
            self.tool_registry,
        )

        logger.success(
            "ToolRegistry initialized."
        )

        # ======================================================
        # TOOL MANAGER
        # ======================================================

        logger.info(
            "Initializing ToolManager..."
        )

        if self.tool_registry is None:

            raise RuntimeError(
                "ToolRegistry was not initialized."
            )

        try:

            self.tool_manager = ToolManager(
                registry=self.tool_registry,
                logger=logger,
            )

        except Exception as exc:

            logger.error(
                f"Failed to initialize ToolManager: {exc}"
            )

            raise

        container.register_singleton(
            "tool_manager",
            self.tool_manager,
        )

        logger.success(
            "ToolManager initialized."
        )

        # ======================================================
        # REGISTER TOOLS
        # ======================================================

        logger.info(
            "Registering application tools..."
        )

        self._register_tools()

        # ------------------------------------------------------
        # Validate registry after registration.
        # ------------------------------------------------------

        try:

            self.tool_registry.validate()

        except Exception as exc:

            logger.error(
                f"Tool registry validation failed: {exc}"
            )

            raise

        logger.success(
            (
                f"Application tools registered successfully. "
                f"Total tools: {self.tool_registry.count}"
            )
        )

        # ------------------------------------------------------
        # Log every registered tool.
        # ------------------------------------------------------

        for tool_name in self.tool_registry.names():

            logger.info(
                f"Registered tool: {tool_name}"
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
        # VOICE INPUT / STT
        # ======================================================

        logger.info(
            "Initializing VoiceInputService..."
        )

        try:

            self.voice_input_service = VoiceInputService(
                api_key=config.groq_api_key,
                model=config.groq_stt_model,
                language=config.voice_input_language,
                logger=logger,
            )

        except Exception as exc:

            logger.error(
                f"Failed to initialize VoiceInputService: {exc}"
            )

            raise

        container.register_singleton(
            "voice_input_service",
            self.voice_input_service,
        )

        logger.success(
            "VoiceInputService initialized."
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

        if self.tool_manager is None:

            raise RuntimeError(
                "ToolManager was not initialized."
            )

        # ------------------------------------------------------
        # IMPORTANT
        #
        # AssistantService receives ToolManager rather than
        # individual tools.
        #
        # This keeps the service independent from concrete
        # tool implementations.
        # ------------------------------------------------------

        self.assistant_service = AssistantService(
            event_bus=event_bus,
            provider=self.provider,
            logger=logger,
            tts_provider=self.tts_provider,
            audio_player=self.audio_player,
            tool_manager=self.tool_manager,
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
            voice_input_service=self.voice_input_service,
        )

        container.register_singleton(
            "assistant_bridge",
            self.bridge,
        )

        logger.success(
            "Assistant bridge initialized."
        )

        # ======================================================
        # FINAL BACKEND VALIDATION
        # ======================================================

        self._validate_backend()

        logger.success(
            "Core services initialized successfully."
        )

    # ==========================================================
    # TOOL REGISTRATION
    # ==========================================================

    def _register_tools(self) -> None:
        """
        Register all application tools.

        Realtime internet tools are registered here.

        Current tools:

            web_search
                ↓
            Search the live internet

            open_url
                ↓
            Open/fetch a live webpage

        Tool implementations remain completely independent
        from AssistantService.
        """

        if self.tool_registry is None:

            raise RuntimeError(
                "ToolRegistry was not initialized."
            )

        logger = log_manager.instance

        # ======================================================
        # REALTIME WEB SEARCH
        # ======================================================

        logger.info(
            "Registering realtime web search tool..."
        )

        try:

            web_search_tool = WebSearchTool(
                logger=logger,
            )

            self.tool_registry.register(
                web_search_tool
            )

        except Exception as exc:

            logger.error(
                (
                    "Failed to register "
                    f"WebSearchTool: {exc}"
                )
            )

            raise

        logger.success(
            "Realtime web search tool registered."
        )

        # ======================================================
        # OPEN URL
        # ======================================================

        logger.info(
            "Registering realtime URL/open tool..."
        )

        try:

            open_tool = OpenTool(
                logger=logger,
            )

            self.tool_registry.register(
                open_tool
            )

        except Exception as exc:

            logger.error(
                (
                    "Failed to register "
                    f"OpenTool: {exc}"
                )
            )

            raise

        logger.success(
            "Realtime URL/open tool registered."
        )

        # ======================================================
        # OPEN APP
        # ======================================================

        logger.info(
            "Registering open app tool..."
        )

        try:

            open_app_tool = OpenAppTool(
                logger=logger,
            )

            self.tool_registry.register(
                open_app_tool
            )

        except Exception as exc:

            logger.error(
                (
                    "Failed to register "
                    f"OpenAppTool: {exc}"
                )
            )

            raise

        logger.success(
            "Open app tool registered."
        )

        # ======================================================
        # FUTURE TOOLS
        # ======================================================
        #
        # Add future tools here:
        #
        # self.tool_registry.register(
        #     CalculatorTool(
        #         logger=logger
        #     )
        # )
        #
        # self.tool_registry.register(
        #     FileSearchTool(
        #         logger=logger
        #     )
        # )
        #
        # self.tool_registry.register(
        #     SystemInfoTool(
        #         logger=logger
        #     )
        # )
        #
        # DO NOT put tool execution logic here.
        #
        # ======================================================

    # ==========================================================
    # BACKEND VALIDATION
    # ==========================================================

    def _validate_backend(self) -> None:
        """
        Validate that all critical backend services exist.
        """

        logger = log_manager.instance

        # ------------------------------------------------------
        # Provider
        # ------------------------------------------------------

        if self.provider is None:

            raise RuntimeError(
                "AI provider is not initialized."
            )

        # ------------------------------------------------------
        # Registry
        # ------------------------------------------------------

        if self.tool_registry is None:

            raise RuntimeError(
                "ToolRegistry is not initialized."
            )

        # ------------------------------------------------------
        # Manager
        # ------------------------------------------------------

        if self.tool_manager is None:

            raise RuntimeError(
                "ToolManager is not initialized."
            )

        # ------------------------------------------------------
        # Tools
        # ------------------------------------------------------

        if self.tool_registry.count == 0:

            raise RuntimeError(
                (
                    "No application tools are registered. "
                    "Krakken cannot perform tool calls."
                )
            )

        # ------------------------------------------------------
        # Required realtime tools
        # ------------------------------------------------------

        required_tools = (
            "web_search",
            "open_url",
        )

        for tool_name in required_tools:

            if not self.tool_registry.contains(
                tool_name
            ):

                raise RuntimeError(
                    (
                        f"Required realtime tool "
                        f"'{tool_name}' is not registered."
                    )
                )

        # ------------------------------------------------------
        # TTS
        # ------------------------------------------------------

        if self.tts_provider is None:

            raise RuntimeError(
                "TTS provider is not initialized."
            )

        # ------------------------------------------------------
        # Audio
        # ------------------------------------------------------

        if self.audio_player is None:

            raise RuntimeError(
                "AudioPlayer is not initialized."
            )

        # ------------------------------------------------------
        # Assistant
        # ------------------------------------------------------

        if self.assistant_service is None:

            raise RuntimeError(
                "AssistantService is not initialized."
            )

        # ------------------------------------------------------
        # Bridge
        # ------------------------------------------------------

        if self.bridge is None:

            raise RuntimeError(
                "AssistantBridge is not initialized."
            )

        logger.success(
            (
                "Backend validation passed. "
                f"{self.tool_registry.count} tools available."
            )
        )

    # ==========================================================
    # RUN APPLICATION
    # ==========================================================

    def run(self) -> int:
        """
        Start the Krakken AI application.
        """

        # ======================================================
        # INITIALIZE BACKEND
        # ======================================================

        self.initialize()

        logger = log_manager.instance

        # ======================================================
        # QT STYLE
        # ======================================================

        QQuickStyle.setStyle(
            "Basic"
        )

        # ======================================================
        # QT APPLICATION
        # ======================================================

        self.app = QGuiApplication(
            sys.argv
        )

        # ======================================================
        # QML ENGINE
        # ======================================================

        self.engine = QQmlApplicationEngine()

        # ======================================================
        # PROJECT PATHS
        # ======================================================

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

        # ======================================================
        # QML IMPORT PATH
        # ======================================================

        self.engine.addImportPath(
            str(qml_root)
        )

        # ======================================================
        # VALIDATE QML ROOT
        # ======================================================

        if not qml_root.exists():

            logger.error(
                f"QML directory not found: {qml_root}"
            )

            raise FileNotFoundError(
                f"QML directory not found: {qml_root}"
            )

        # ======================================================
        # VALIDATE BRIDGE
        # ======================================================

        if self.bridge is None:

            raise RuntimeError(
                "AssistantBridge was not initialized."
            )

        # ======================================================
        # EXPOSE BRIDGE TO QML
        # ======================================================
        #
        # IMPORTANT:
        #
        # We intentionally use:
        #
        #     krakkenBridge
        #
        # instead of:
        #
        #     assistantBridge
        #
        # ChatView already has a property named
        # assistantBridge.
        #
        # Using the same name caused QML scope-resolution
        # conflicts.
        #
        # ======================================================

        self.engine.rootContext().setContextProperty(
            "krakkenBridge",
            self.bridge,
        )

        logger.success(
            (
                "Assistant bridge exposed to QML "
                "as 'krakkenBridge'."
            )
        )

        # ======================================================
        # MAIN QML
        # ======================================================

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

        # ======================================================
        # LOAD QML
        # ======================================================

        self.engine.load(
            QUrl.fromLocalFile(
                str(qml_file)
            )
        )

        # ======================================================
        # VERIFY QML
        # ======================================================

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

        # ======================================================
        # APPLICATION READY
        # ======================================================

        logger.success(
            "UI loaded successfully."
        )

        logger.success(
            (
                "Krakken AI is running with "
                f"{self.tool_registry.count if self.tool_registry else 0} "
                "registered tools."
            )
        )

        # ======================================================
        # QT EVENT LOOP
        # ======================================================

        return self.app.exec()
