"""
Krakken AI - Assistant Bridge.

Connects the QML frontend with the Python AI backend.

The bridge is responsible only for communication between
QML and the EventBus.

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

Important:
EventBus callbacks may execute on background worker threads.

All UI-affecting communication is therefore marshalled
through Qt queued signals.

IMPORTANT:
Response lifecycle events use ONE ordered Qt relay signal.

This prevents:

    responseFinished
        ↓
    being delivered before the final response chunks.

Using separate queued signals for chunks and finished can
allow them to be processed out of order.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from core.events.event_bus import Event, EventBus


class AssistantBridge(QObject):
    """
    Qt/QML bridge for the Krakken AI assistant.

    EventBus callbacks may originate from worker threads.

    The bridge therefore forwards UI updates through Qt's
    event loop before emitting public QML signals.
    """

    # ==========================================================
    # QML OUTPUT SIGNALS
    # ==========================================================

    stateChanged = Signal(str)

    responseStarted = Signal()

    responseChunk = Signal(str)

    responseFinished = Signal()

    errorOccurred = Signal(str)

    highlightsReady = Signal(str)

    # ==========================================================
    # ORDERED RESPONSE RELAY
    #
    # IMPORTANT:
    #
    # All response lifecycle events travel through this ONE
    # signal.
    #
    # This guarantees ordering:
    #
    # started
    # chunk
    # chunk
    # chunk
    # finished
    #
    # instead of using separate queued signals that may be
    # delivered in an unexpected order.
    # ==========================================================

    _responseRelay = Signal(str, str)

    # ==========================================================
    # OTHER QT RELAYS
    # ==========================================================

    _stateRelay = Signal(str)

    _errorRelay = Signal(str)

    _highlightsRelay = Signal(str)

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        event_bus: EventBus | None = None,
        logger: Any = None,
    ) -> None:

        super().__init__()

        self.event_bus = event_bus
        self.logger = logger

        self._state = "idle"

        # ------------------------------------------------------
        # Ordered response relay.
        #
        # Every response event enters Qt through this single
        # queued connection.
        # ------------------------------------------------------

        self._responseRelay.connect(
            self._handle_response_relay,
            Qt.ConnectionType.QueuedConnection,
        )

        # ------------------------------------------------------
        # Other relays.
        # ------------------------------------------------------

        self._stateRelay.connect(
            self._emit_state,
            Qt.ConnectionType.QueuedConnection,
        )

        self._errorRelay.connect(
            self._emit_error,
            Qt.ConnectionType.QueuedConnection,
        )

        self._highlightsRelay.connect(
            self._emit_highlights,
            Qt.ConnectionType.QueuedConnection,
        )

        # ------------------------------------------------------
        # Subscribe to backend → UI events.
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
                "assistant.highlights",
                self._on_assistant_highlights,
            )

        self._log(
            "AssistantBridge initialized."
        )

    # ==========================================================
    # STATE
    # ==========================================================

    @property
    def state(self) -> str:
        """
        Return the current assistant state.
        """

        return self._state

    def set_state(
        self,
        state: str,
    ) -> None:
        """
        Update the internal assistant state.

        This method may be called from any thread.
        """

        if not state:
            return

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
    # QML → EVENT BUS
    # ==========================================================

    @Slot(str)
    def sendMessage(
        self,
        message: str,
    ) -> None:
        """
        Receive a message from QML and publish it
        to the EventBus.
        """

        if not message:
            return

        message = message.strip()

        if not message:
            return

        self._log(
            f"Message received: {message}"
        )

        if self.event_bus is None:

            self._handle_error(
                "EventBus is not available."
            )

            return

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
    # HIGHLIGHTS
    # ==========================================================

    def _on_assistant_highlights(
        self,
        event: Event,
    ) -> None:
        """
        Receive AI-generated highlights from the backend.

        This callback may execute on a worker thread.
        """

        highlights = event.payload.get(
            "highlights",
            "",
        )

        if not highlights:
            return

        highlights = str(
            highlights
        )

        self._log(
            "AI highlights received."
        )

        self._log(
            f"AI HIGHLIGHTS: {highlights!r}"
        )

        self._highlightsRelay.emit(
            highlights
        )

    def _emit_highlights(
        self,
        highlights: str,
    ) -> None:
        """
        Emit highlights from the Qt GUI thread.
        """

        if not highlights:
            return

        try:

            self.highlightsReady.emit(
                highlights
            )

        except Exception as exc:

            self._log(
                f"Failed to emit highlights: {exc}",
                error=True,
            )

    # ==========================================================
    # RESPONSE STARTED
    # ==========================================================

    def _on_response_started(
        self,
        event: Event,
    ) -> None:
        """
        Receive response-start event from backend.

        This callback may run on a worker thread.
        """

        self._log(
            "Assistant response started."
        )

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
        """
        Receive a streamed AI response chunk.

        EventBus may call this from the AI worker thread.

        IMPORTANT:
        The chunk is sent through the same relay signal used
        by responseFinished.
        """

        response = event.payload.get(
            "response",
            "",
        )

        if not response:
            return

        response = str(
            response
        )

        self._log(
            f"AI CHUNK RECEIVED BY BRIDGE: {response!r}"
        )

        self._responseRelay.emit(
            "chunk",
            response,
        )

    # ==========================================================
    # RESPONSE FINISHED
    # ==========================================================

    def _on_response_finished(
        self,
        event: Event,
    ) -> None:
        """
        Receive response-finished event from backend.

        This is deliberately sent through the same relay as
        response chunks.

        Therefore:

            chunk
            chunk
            chunk
            finished

        remains ordered when entering the Qt event loop.
        """

        self._log(
            "Assistant response finished."
        )

        self._responseRelay.emit(
            "finished",
            "",
        )

    # ==========================================================
    # ORDERED RESPONSE RELAY HANDLER
    # ==========================================================

    @Slot(str, str)
    def _handle_response_relay(
        self,
        event_type: str,
        data: str,
    ) -> None:
        """
        Handle ordered response events on the Qt GUI thread.
        """

        try:

            if event_type == "started":

                self._log(
                    "AI RESPONSE STARTED → QML"
                )

                self.responseStarted.emit()

                return

            if event_type == "chunk":

                if not data:
                    return

                self._log(
                    f"AI CHUNK FORWARDED TO QML: {data!r}"
                )

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
                f"Failed to handle response relay: {exc}",
                error=True,
            )

    # ==========================================================
    # STATE EVENT
    # ==========================================================

    def _on_assistant_state(
        self,
        event: Event,
    ) -> None:
        """
        Receive backend state changes.
        """

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
    # STATE QT EMISSION
    # ==========================================================

    def _emit_state(
        self,
        state: str,
    ) -> None:
        """
        Emit stateChanged from the Qt GUI thread.
        """

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
    # ERROR EVENT
    # ==========================================================

    def _on_assistant_error(
        self,
        event: Event,
    ) -> None:
        """
        Receive backend errors.
        """

        error = event.payload.get(
            "error",
            "Unknown assistant error.",
        )

        self._handle_error(
            str(error)
        )

    # ==========================================================
    # ERROR HANDLING
    # ==========================================================

    def _handle_error(
        self,
        message: str,
    ) -> None:
        """
        Handle an assistant error.

        This method may be called from a worker thread.
        """

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

    def _emit_error(
        self,
        message: str,
    ) -> None:
        """
        Emit the error signal from the Qt GUI thread.
        """

        try:

            self.errorOccurred.emit(
                message
            )

        except Exception as exc:

            self._log(
                f"Failed to emit error: {exc}",
                error=True,
            )

    # ==========================================================
    # CLEAR CONVERSATION
    # ==========================================================

    @Slot()
    def clearConversation(self) -> None:
        """
        Request conversation history to be cleared.
        """

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

            self._log(
                "Conversation clear request published."
            )

        except Exception as exc:

            self._handle_error(
                f"Failed to clear conversation: {exc}"
            )

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def shutdown(self) -> None:
        """
        Shut down the bridge.
        """

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
        """
        Safely write to the Krakken logger.
        """

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