
"""
Krakken AI — Assistant.

High-level assistant orchestration layer.

Architecture:

    User Input
        ↓
    Assistant
        ↓
    LLM Provider
        ↓
    Final Response
        ↓
    ResponseHandler
        ↓
    SpeechIntegration
        ↓
    SpeechBridge
        ↓
    SpeechController
        ↓
    TTS / Audio

The Assistant intentionally knows nothing about:

- Kokoro
- TTS models
- audio devices
- audio playback
- speech queues
- TTS workers
- UI implementation

It coordinates the LLM provider and finalized
assistant response handling.
"""

from __future__ import annotations

from typing import Any, Optional


class Assistant:
    """
    High-level assistant coordinator.

    Responsibilities:

    1. Initialize the LLM provider.
    2. Accept user input.
    3. Generate a finalized assistant response.
    4. Forward the response to ResponseHandler.
    5. Manage assistant lifecycle.
    """

    def __init__(
        self,
        *,
        llm_provider: Any,
        response_handler: Any = None,
        logger: Any = None,
    ) -> None:

        if llm_provider is None:
            raise ValueError(
                "llm_provider cannot be None."
            )

        self._llm_provider = llm_provider
        self._response_handler = response_handler
        self._logger = logger

        self._initialized = False

        self._log(
            "Assistant created."
        )

    # ==================================================
    # INITIALIZATION
    # ==================================================

    def initialize(self) -> None:
        """
        Initialize the assistant and its LLM provider.
        """

        if self._initialized:
            return

        self._log(
            "Initializing Assistant..."
        )

        try:

            initialize = getattr(
                self._llm_provider,
                "initialize",
                None,
            )

            if callable(initialize):
                initialize()

            self._initialized = True

            self._log(
                "Assistant initialized."
            )

        except Exception as exc:

            self._initialized = False

            self._log(
                f"Assistant initialization failed: {exc}",
                error=True,
            )

            raise

    # ==================================================
    # ASK
    # ==================================================

    def ask(
        self,
        message: str,
    ) -> str:
        """
        Send a user message to the LLM provider.

        The finalized response is forwarded to the
        ResponseHandler when one is configured.

        Args:
            message:
                User input.

        Returns:
            Final assistant response.

        Raises:
            ValueError:
                If the message is empty or contains
                only whitespace.
            RuntimeError:
                If the LLM provider returns no response.
        """

        # --------------------------------------------------
        # INPUT VALIDATION
        # --------------------------------------------------

        if not message or not message.strip():

            self._log(
                "Rejecting empty assistant request."
            )

            raise ValueError(
                "Assistant message cannot be empty."
            )

        # --------------------------------------------------
        # INITIALIZE
        # --------------------------------------------------

        if not self._initialized:
            self.initialize()

        message = message.strip()

        self._log(
            f"Assistant request: {message[:100]!r}"
        )

        try:

            # ----------------------------------------------
            # GENERATE RESPONSE
            # ----------------------------------------------

            response = self._generate_response(
                message
            )

            # ----------------------------------------------
            # VALIDATE LLM RESPONSE
            # ----------------------------------------------

            if response is None:

                self._log(
                    "LLM provider returned no response.",
                    error=True,
                )

                raise RuntimeError(
                    "LLM provider returned no response."
                )

            response = str(
                response
            ).strip()

            if not response:

                self._log(
                    "LLM provider returned an empty response.",
                    error=True,
                )

                raise RuntimeError(
                    "LLM provider returned an empty response."
                )

            self._log(
                f"Assistant response received: "
                f"{response[:100]!r}"
            )

            # ----------------------------------------------
            # FORWARD FINAL RESPONSE
            # ----------------------------------------------

            if self._response_handler is not None:

                self._response_handler.handle(
                    response
                )

                self._log(
                    "Response forwarded to ResponseHandler."
                )

            return response

        except Exception as exc:

            self._log(
                f"Assistant request failed: {exc}",
                error=True,
            )

            raise

    # ==================================================
    # RESPONSE GENERATION
    # ==================================================

    def _generate_response(
        self,
        message: str,
    ) -> Any:
        """
        Generate a response using the configured
        LLM provider.

        Supported provider interfaces:

            generate(message)
            complete(message)
            chat(message)
            ask(message)
        """

        provider = self._llm_provider

        # ------------------------------------------
        # GENERATE
        # ------------------------------------------

        generate = getattr(
            provider,
            "generate",
            None,
        )

        if callable(generate):

            return generate(
                message
            )

        # ------------------------------------------
        # COMPLETE
        # ------------------------------------------

        complete = getattr(
            provider,
            "complete",
            None,
        )

        if callable(complete):

            return complete(
                message
            )

        # ------------------------------------------
        # CHAT
        # ------------------------------------------

        chat = getattr(
            provider,
            "chat",
            None,
        )

        if callable(chat):

            return chat(
                message
            )

        # ------------------------------------------
        # ASK
        # ------------------------------------------

        ask = getattr(
            provider,
            "ask",
            None,
        )

        if callable(ask):

            return ask(
                message
            )

        raise AttributeError(
            "LLM provider does not expose a supported "
            "response method. Expected one of: "
            "generate(), complete(), chat(), ask()."
        )

    # ==================================================
    # RESPONSE HANDLER
    # ==================================================

    def set_response_handler(
        self,
        response_handler: Any,
    ) -> None:
        """
        Attach or replace the ResponseHandler.
        """

        self._response_handler = response_handler

        self._log(
            "ResponseHandler attached."
        )

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_initialized(self) -> bool:
        """
        Return whether the Assistant is initialized.
        """

        return self._initialized

    @property
    def response_handler(self) -> Any:
        """
        Return the configured ResponseHandler.
        """

        return self._response_handler

    @property
    def llm_provider(self) -> Any:
        """
        Return the configured LLM provider.

        Useful for diagnostics and testing.
        """

        return self._llm_provider

    # ==================================================
    # SPEECH STATUS
    # ==================================================

    @property
    def is_speaking(self) -> bool:
        """
        Return whether the assistant is currently speaking.
        """

        if self._response_handler is None:
            return False

        return bool(
            getattr(
                self._response_handler,
                "is_speaking",
                False,
            )
        )

    @property
    def pending_speech(self) -> int:
        """
        Return the number of pending speech requests.
        """

        if self._response_handler is None:
            return 0

        return int(
            getattr(
                self._response_handler,
                "pending_speech",
                0,
            )
        )

    # ==================================================
    # SPEECH CONTROL
    # ==================================================

    def enable_speech(self) -> None:
        """
        Enable assistant speech output.
        """

        if self._response_handler is None:
            return

        enable = getattr(
            self._response_handler,
            "enable_speech",
            None,
        )

        if callable(enable):
            enable()

        self._log(
            "Assistant speech enabled."
        )

    def disable_speech(
        self,
        *,
        stop_current: bool = True,
    ) -> None:
        """
        Disable assistant speech output.

        Args:
            stop_current:
                Whether currently playing speech
                should be stopped.
        """

        if self._response_handler is None:
            return

        disable = getattr(
            self._response_handler,
            "disable_speech",
            None,
        )

        if callable(disable):

            disable(
                stop_current=stop_current
            )

        self._log(
            "Assistant speech disabled."
        )

    def stop_speech(self) -> None:
        """
        Stop the current assistant speech.
        """

        if self._response_handler is None:
            return

        stop = getattr(
            self._response_handler,
            "stop_speech",
            None,
        )

        if callable(stop):
            stop()

        self._log(
            "Assistant speech stopped."
        )

    # ==================================================
    # SHUTDOWN
    # ==================================================

    def shutdown(self) -> None:
        """
        Shut down the assistant.

        ResponseHandler and LLM provider are shut down
        when they expose shutdown() methods.
        """

        self._log(
            "Shutting down Assistant..."
        )

        # ------------------------------------------
        # RESPONSE HANDLER
        # ------------------------------------------

        if self._response_handler is not None:

            try:

                shutdown = getattr(
                    self._response_handler,
                    "shutdown",
                    None,
                )

                if callable(shutdown):
                    shutdown()

            except Exception as exc:

                self._log(
                    f"ResponseHandler shutdown failed: {exc}",
                    error=True,
                )

        # ------------------------------------------
        # LLM PROVIDER
        # ------------------------------------------

        try:

            shutdown = getattr(
                self._llm_provider,
                "shutdown",
                None,
            )

            if callable(shutdown):
                shutdown()

        except Exception as exc:

            self._log(
                f"LLM provider shutdown failed: {exc}",
                error=True,
            )

        self._initialized = False

        self._log(
            "Assistant shutdown complete."
        )

    # ==================================================
    # LOGGING
    # ==================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:
        """
        Safely write to Krakken's logger.
        """

        if self._logger is None:
            return

        try:

            if error:

                self._logger.error(
                    message
                )

            else:

                self._logger.info(
                    message
                )

        except Exception:
            pass

