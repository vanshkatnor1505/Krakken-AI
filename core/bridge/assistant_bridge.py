
"""
Krakken AI - Assistant Bridge.

Connects the QML frontend with the Python AI backend.

Architecture:

    QML
      ↓
    AssistantBridge
      ↓
    EventBus
      ↓
    AssistantService
      ↓
    GroqProvider
      ↓
    Groq API
      ↓
    AssistantService
      ↓
    EventBus
      ↓
    AssistantBridge
      ↓
    QML
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Property,
    QObject,
    Qt,
    Signal,
    Slot,
)

from core.events.event_bus import Event, EventBus
from core.voice.voice_input_service import (
    VoiceInputService,
    VoiceInputServiceError,
)


class AssistantBridge(QObject):
    """
    Qt/QML bridge between the Python backend and QML frontend.
    """

    # ==========================================================
    # QML SIGNALS
    # ==========================================================

    stateChanged = Signal(str)

    responseStarted = Signal()

    responseChunk = Signal(str)

    responseFinished = Signal()

    errorOccurred = Signal(str)

    historyCleared = Signal()

    highlightsReady = Signal(list)

    transcriptReady = Signal(str)

    recordingChanged = Signal(bool)

    # ==========================================================
    # INTERNAL RELAYS
    #
    # These signals are emitted from EventBus/background threads
    # and handled on the Qt GUI thread.
    # ==========================================================

    _responseRelay = Signal(str, str)

    _stateRelay = Signal(str)

    _errorRelay = Signal(str)

    _historyClearedRelay = Signal()

    _highlightsRelay = Signal(list)

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(
        self,
        event_bus: EventBus | None = None,
        logger: Any = None,
        voice_input_service: VoiceInputService | None = None,
    ) -> None:

        super().__init__()

        self.event_bus = event_bus
        self.logger = logger
        self.voice_input_service = voice_input_service

        self._state = "idle"
        self._is_recording = False

        # ------------------------------------------------------
        # Internal Qt relays
        # ------------------------------------------------------

        self._responseRelay.connect(
            self._handle_response_relay,
            Qt.ConnectionType.QueuedConnection,
        )

        self._stateRelay.connect(
            self._emit_state,
            Qt.ConnectionType.QueuedConnection,
        )

        self._errorRelay.connect(
            self._emit_error,
            Qt.ConnectionType.QueuedConnection,
        )

        self._historyClearedRelay.connect(
            self._emit_history_cleared,
            Qt.ConnectionType.QueuedConnection,
        )

        self._highlightsRelay.connect(
            self._emit_highlights,
            Qt.ConnectionType.QueuedConnection,
        )

        # ------------------------------------------------------
        # Subscribe to EventBus
        # ------------------------------------------------------

        if self.event_bus is not None:

            self.event_bus.subscribe(
                "assistant.response.started",
                self._on_response_started,
            )

            self.event_bus.subscribe(
                "assistant.response",
                self._on_assistant_response,
            )

            self.event_bus.subscribe(
                "assistant.response.finished",
                self._on_response_finished,
            )

            self.event_bus.subscribe(
                "assistant.state",
                self._on_assistant_state,
            )

            self.event_bus.subscribe(
                "assistant.error",
                self._on_assistant_error,
            )

            self.event_bus.subscribe(
                "assistant.history.cleared",
                self._on_history_cleared,
            )

            self.event_bus.subscribe(
                "assistant.highlights",
                self._on_highlights,
            )

        self._log(
            "AssistantBridge initialized."
        )

    # ==========================================================
    # QML PROPERTY
    # ==========================================================

    def _get_state(self) -> str:
        return self._state

    state = Property(
        str,
        _get_state,
        notify=stateChanged,
    )

    def _get_is_recording(self) -> bool:
        return self._is_recording

    isRecording = Property(
        bool,
        _get_is_recording,
        notify=recordingChanged,
    )

    # ==========================================================
    # STATE
    # ==========================================================

    def set_state(
        self,
        state: str,
    ) -> None:

        if not state:
            return

        state = str(state)

        if state == self._state:
            return

        self._state = state

        self._log(
            f"AI state changed: {state}"
        )

        self._stateRelay.emit(
            state
        )

    # ==========================================================
    # VOICE INPUT
    # ==========================================================

    @Slot()
    def startVoiceInput(self) -> None:
        if self.voice_input_service is None:
            self._handle_error(
                "Voice input service is not available."
            )
            return

        if self._is_recording:
            return

        try:
            self.voice_input_service.start_recording()
            self._is_recording = True
            self.recordingChanged.emit(True)
            self.set_state("recording")
            self._log("Voice recording started.")

        except Exception as exc:
            self._handle_error(
                f"Failed to start voice recording: {exc}"
            )

    @Slot()
    def stopVoiceInput(self) -> None:
        if self.voice_input_service is None:
            self._handle_error(
                "Voice input service is not available."
            )
            return

        if not self._is_recording and not self.voice_input_service.is_recording:
            return

        self._is_recording = False
        self.recordingChanged.emit(False)
        self.set_state("processing")

        def _transcribe() -> None:
            try:
                transcript = self.voice_input_service.capture_and_transcribe()

                if not transcript:
                    self._log("Voice input produced an empty transcript.")
                    self.set_state("idle")
                    return

                self.set_state("idle")
                self.transcriptReady.emit(transcript)

            except VoiceInputServiceError as exc:
                self._handle_error(str(exc))

            except Exception as exc:
                self._handle_error(
                    f"Voice transcription failed: {exc}"
                )

        from threading import Thread

        Thread(
            target=_transcribe,
            name="Krakken-Voice-STT",
            daemon=True,
        ).start()

    @Slot()
    def toggleVoiceInput(self) -> None:
        if self._is_recording:
            self.stopVoiceInput()
        else:
            self.startVoiceInput()

    # ==========================================================
    # QML → BACKEND
    # ==========================================================

    @Slot(str)
    def sendMessage(
        self,
        message: str,
    ) -> None:

        if not message:
            return

        message = message.strip()

        if not message:
            return

        if self.event_bus is None:

            self._handle_error(
                "EventBus is not available."
            )

            return

        self._log(
            "Message received from QML."
        )

        try:

            self.set_state(
                "thinking"
            )

            self.event_bus.publish(
                Event(
                    name="assistant.message",
                    payload={
                        "message": message,
                    },
                )
            )

        except Exception as exc:

            self._handle_error(
                f"Failed to send message: {exc}"
            )

    # ==========================================================
    # RESPONSE STARTED
    # ==========================================================

    def _on_response_started(
        self,
        event: Event,
    ) -> None:

        self._responseRelay.emit(
            "started",
            "",
        )

    # ==========================================================
    # RESPONSE CHUNK
    # ==========================================================

    def _on_assistant_response(
        self,
        event: Event,
    ) -> None:

        response = event.payload.get(
            "response",
            "",
        )

        if not response:
            return

        self._responseRelay.emit(
            "chunk",
            str(response),
        )

    # ==========================================================
    # RESPONSE FINISHED
    # ==========================================================

    def _on_response_finished(
        self,
        event: Event,
    ) -> None:

        self._responseRelay.emit(
            "finished",
            "",
        )

    # ==========================================================
    # RESPONSE RELAY
    # ==========================================================

    @Slot(str, str)
    def _handle_response_relay(
        self,
        event_type: str,
        data: str,
    ) -> None:

        try:

            if event_type == "started":

                self._log(
                    "AI RESPONSE STARTED → QML"
                )

                self.responseStarted.emit()

                return

            if event_type == "chunk":

                if data:

                    self.responseChunk.emit(
                        data
                    )

                return

            if event_type == "finished":

                self._log(
                    "AI RESPONSE FINISHED → QML"
                )

                self.responseFinished.emit()

                return

            self._log(
                f"Unknown response relay event: {event_type}",
                error=True,
            )

        except Exception as exc:

            self._log(
                f"Response relay error: {exc}",
                error=True,
            )

    # ==========================================================
    # STATE EVENT
    # ==========================================================

    def _on_assistant_state(
        self,
        event: Event,
    ) -> None:

        state = event.payload.get(
            "state",
            "",
        )

        if not state:
            return

        self.set_state(
            str(state)
        )

    # ==========================================================
    # STATE EMISSION
    # ==========================================================

    @Slot(str)
    def _emit_state(
        self,
        state: str,
    ) -> None:

        try:

            self.stateChanged.emit(
                state
            )

        except Exception as exc:

            self._log(
                f"Failed to emit stateChanged: {exc}",
                error=True,
            )

    # ==========================================================
    # HIGHLIGHTS
    # ==========================================================

    def _on_highlights(
        self,
        event: Event,
    ) -> None:

        highlights = event.payload.get(
            "highlights",
            [],
        )

        if highlights is None:
            highlights = []

        if not isinstance(
            highlights,
            list,
        ):
            highlights = list(highlights)

        self._highlightsRelay.emit(
            highlights
        )

    # ==========================================================
    # HIGHLIGHTS EMISSION
    # ==========================================================

    @Slot(list)
    def _emit_highlights(
        self,
        highlights: list,
    ) -> None:

        try:

            self.highlightsReady.emit(
                highlights
            )

        except Exception as exc:

            self._log(
                f"Failed to emit highlightsReady: {exc}",
                error=True,
            )

    # ==========================================================
    # ERROR EVENT
    # ==========================================================

    def _on_assistant_error(
        self,
        event: Event,
    ) -> None:

        error = event.payload.get(
            "error",
            "Unknown assistant error.",
        )

        self._handle_error(
            str(error)
        )

    def _handle_error(
        self,
        message: str,
    ) -> None:

        self._log(
            f"Assistant error: {message}",
            error=True,
        )

        self._state = "error"

        self._errorRelay.emit(
            message
        )

        self._stateRelay.emit(
            "error"
        )

    # ==========================================================
    # ERROR EMISSION
    # ==========================================================

    @Slot(str)
    def _emit_error(
        self,
        message: str,
    ) -> None:

        try:

            self.errorOccurred.emit(
                message
            )

        except Exception as exc:

            self._log(
                f"Failed to emit errorOccurred: {exc}",
                error=True,
            )

    # ==========================================================
    # CLEAR HISTORY
    # ==========================================================

    @Slot()
    def clearConversation(
        self,
    ) -> None:

        if self.event_bus is None:

            self._handle_error(
                "EventBus is not available."
            )

            return

        try:

            self.event_bus.publish(
                Event(
                    name="assistant.clear_history",
                    payload={},
                )
            )

        except Exception as exc:

            self._handle_error(
                f"Failed to clear conversation: {exc}"
            )

    # ==========================================================
    # HISTORY CLEARED
    # ==========================================================

    def _on_history_cleared(
        self,
        event: Event,
    ) -> None:

        self._historyClearedRelay.emit()

    @Slot()
    def _emit_history_cleared(
        self,
    ) -> None:

        self.historyCleared.emit()

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def shutdown(
        self,
    ) -> None:

        self._log(
            "AssistantBridge shutdown."
        )

    # ==========================================================
    # LOGGING
    # ==========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:

        if self.logger is None:
            return

        try:

            if error:

                self.logger.error(
                    message
                )

            else:

                self.logger.info(
                    message
                )

        except Exception:
            pass

