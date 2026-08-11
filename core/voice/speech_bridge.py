
"""
Krakken AI - Speech Bridge.

Connects Krakken's assistant response system to the
voice subsystem.

Architecture:

    Assistant Response
            ↓
      SpeechBridge
            ↓
      SpeechController
            ↓
        TTSWorker
            ↓
          Kokoro
            ↓
        SpeechQueue
            ↓
        AudioPlayer
            ↓
         Speakers

SpeechBridge intentionally knows nothing about:

- Kokoro
- TTS providers
- Audio devices
- Audio queues
- QML
- LLM implementation

Its only responsibility is deciding whether a response
should be forwarded to SpeechController.
"""

from __future__ import annotations

from typing import Any, Optional


class SpeechBridge:
    """
    Connects assistant responses to SpeechController.

    The bridge is intentionally lightweight. It should sit
    between the assistant/brain layer and the voice subsystem.
    """

    def __init__(
        self,
        speech_controller: Any,
        logger: Any = None,
        enabled: bool = True,
    ) -> None:
        """
        Create a SpeechBridge.

        Args:
            speech_controller:
                Initialized SpeechController instance.

            logger:
                Optional Krakken logger.

            enabled:
                Whether speech output is enabled.
        """

        if speech_controller is None:
            raise ValueError(
                "speech_controller cannot be None."
            )

        self._speech_controller = speech_controller
        self._logger = logger
        self._enabled = enabled

        self._log(
            "SpeechBridge created."
        )

    # ==================================================
    # SPEAK
    # ==================================================

    def speak(
        self,
        text: str,
    ) -> Optional[int]:
        """
        Send assistant text to the speech controller.

        This method does not perform synthesis itself.

        Returns:
            Sequence number returned by SpeechController,
            if available.
        """

        if not self._enabled:
            self._log(
                "SpeechBridge is disabled."
            )
            return None

        if not text or not text.strip():
            self._log(
                "Ignoring empty speech request."
            )
            return None

        text = text.strip()

        self._log(
            f"Forwarding speech request: {text[:100]!r}"
        )

        try:
            sequence = self._speech_controller.speak(
                text
            )

            self._log(
                f"Speech request forwarded. "
                f"Sequence: {sequence}"
            )

            return sequence

        except Exception as exc:
            self._log(
                f"Failed to forward speech request: {exc}",
                error=True,
            )
            raise

    # ==================================================
    # ENABLE / DISABLE
    # ==================================================

    def enable(self) -> None:
        """
        Enable speech output.
        """

        self._enabled = True

        self._log(
            "SpeechBridge enabled."
        )

    def disable(
        self,
        *,
        stop_current: bool = True,
    ) -> None:
        """
        Disable speech output.

        Args:
            stop_current:
                If True, stop speech that is currently playing.
        """

        self._enabled = False

        self._log(
            "SpeechBridge disabled."
        )

        if stop_current:
            self.stop()

    @property
    def enabled(self) -> bool:
        """
        Return whether speech output is enabled.
        """

        return self._enabled

    # ==================================================
    # STOP
    # ==================================================

    def stop(self) -> None:
        """
        Stop current speech.

        The actual stopping is delegated to
        SpeechController.
        """

        try:
            self._speech_controller.stop()

            self._log(
                "Speech playback stopped."
            )

        except Exception as exc:
            self._log(
                f"Failed to stop speech: {exc}",
                error=True,
            )
            raise

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_speaking(self) -> bool:
        """
        Return whether Krakken is currently speaking.

        Uses SpeechController as the source of truth.
        """

        try:
            return bool(
                self._speech_controller.is_speaking
            )

        except AttributeError:
            return False

    @property
    def pending(self) -> int:
        """
        Return the number of pending speech requests.

        If SpeechController does not expose pending state,
        return zero.
        """

        try:
            return int(
                self._speech_controller.pending
            )

        except AttributeError:
            return 0

    # ==================================================
    # SHUTDOWN
    # ==================================================

    def shutdown(self) -> None:
        """
        Shut down the speech subsystem.

        SpeechBridge itself owns no worker/model resources,
        so shutdown is delegated to SpeechController.
        """

        self._log(
            "Shutting down SpeechBridge..."
        )

        try:
            self._speech_controller.shutdown()

        finally:
            self._enabled = False

        self._log(
            "SpeechBridge shutdown complete."
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
                self._logger.error(message)
            else:
                self._logger.info(message)

        except Exception:
            pass

