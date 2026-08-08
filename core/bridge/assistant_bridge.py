"""
Krakken AI - Assistant Bridge.

Connects the QML frontend with the Python AI backend.

The bridge is only responsible for communication between
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

The bridge does NOT call Groq directly.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from core.events.event_bus import Event, EventBus


class AssistantBridge(QObject):
    """
    Qt/QML bridge for the Krakken AI assistant.
    """

    # ==========================================================
    # QML OUTPUT SIGNALS
    # ==========================================================

    stateChanged = Signal(str)

    responseStarted = Signal()

    responseChunk = Signal(str)

    responseFinished = Signal()

    errorOccurred = Signal(str)

    # ----------------------------------------------------------
    # AI GENERATED HIGHLIGHTS
    # ----------------------------------------------------------

    highlightsReady = Signal(str)

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
        # Subscribe to backend -> UI events
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

            # --------------------------------------------------
            # AI generated highlights
            # --------------------------------------------------

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
        Update the assistant state and notify QML.
        """

        if not state:
            return

        if state == self._state:
            return

        self._state = state

        self._log(
            f"AI state changed: {state}"
        )

        self.stateChanged.emit(
            state
        )

    # ==========================================================
    # QML -> EVENT BUS
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
        Forward AI-generated highlights to QML.
        """

        highlights = event.payload.get(
            "highlights",
            "",
        )

        if not highlights:
            return

        try:

            self._log(
                "AI highlights received."
            )

            self.highlightsReady.emit(
                str(highlights)
            )

        except Exception as exc:

            self._handle_error(
                str(exc)
            )

    # ==========================================================
    # RESPONSE STARTED
    # ==========================================================

    def _on_response_started(
        self,
        event: Event,
    ) -> None:
        """
        Notify QML that an AI response has started.
        """

        try:

            self._log(
                "Assistant response started."
            )

            self.responseStarted.emit()

        except Exception as exc:

            self._handle_error(
                str(exc)
            )

    # ==========================================================
    # RESPONSE CHUNK
    # ==========================================================

    def _on_assistant_response(
        self,
        event: Event,
    ) -> None:
        """
        Forward a streamed AI response chunk to QML.
        """

        response = event.payload.get(
            "response",
            "",
        )

        if not response:
            return

        self._log(
            f"AI CHUNK FORWARDED TO QML: {response!r}"
        )

        try:

            self.responseChunk.emit(
                str(response)
            )

        except Exception as exc:

            self._handle_error(
                str(exc)
            )

    # ==========================================================
    # RESPONSE FINISHED
    # ==========================================================

    def _on_response_finished(
        self,
        event: Event,
    ) -> None:
        """
        Notify QML that the AI response is complete.
        """

        try:

            self._log(
                "Assistant response finished."
            )

            self.responseFinished.emit()

        except Exception as exc:

            self._handle_error(
                str(exc)
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
        Handle an assistant error and notify QML.
        """

        self._log(
            f"Assistant error: {message}",
            error=True,
        )

        self.set_state(
            "error"
        )

        self.errorOccurred.emit(
            message
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
        Safely write to the Kraken logger.
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