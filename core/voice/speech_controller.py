
"""
Krakken AI - Speech Controller.

High-level orchestration layer for Krakken's voice output.

Architecture:

    Assistant
        ↓
    SpeechController
        ↓
    SpeechQueue
        ↓
    TTSWorker
        ↓
    TTSProvider
        ↓
    AudioData
        ↓
    AudioPlayer
        ↓
    Speakers

SpeechController intentionally hides:

- Kokoro
- TTS worker threads
- audio devices
- PCM handling
- playback implementation

The rest of Krakken should interact with this class
instead of directly interacting with the lower-level
voice components.
"""

from __future__ import annotations

from typing import Any, Optional

from core.voice.providers.kokoro_provider import KokoroProvider
from core.voice.audio_player import AudioPlayer
from core.voice.speech_queue import SpeechQueue
from core.voice.tts_worker import TTSWorker


class SpeechController:
    """
    High-level controller for Krakken speech output.
    """

    def __init__(
        self,
        *,
        voice: str = "af_heart",
        speed: float = 1.0,
        logger: Any = None,
    ) -> None:

        self.voice = voice
        self.speed = speed
        self.logger = logger

        self._provider: Optional[KokoroProvider] = None
        self._player: Optional[AudioPlayer] = None
        self._worker: Optional[TTSWorker] = None
        self._queue: Optional[SpeechQueue] = None

        self._initialized = False

        self._log(
            "SpeechController created."
        )

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def initialize(self) -> None:
        """
        Initialize the complete speech subsystem.

        This performs the expensive Kokoro initialization once.
        """

        if self._initialized:
            return

        self._log(
            "Initializing SpeechController..."
        )

        try:

            # ------------------------------------------------
            # TTS PROVIDER
            # ------------------------------------------------

            self._provider = KokoroProvider(
                voice=self.voice,
                speed=self.speed,
                logger=self.logger,
            )

            self._provider.initialize()

            # ------------------------------------------------
            # AUDIO PLAYER
            # ------------------------------------------------

            self._player = AudioPlayer(
                logger=self.logger,
            )

            # ------------------------------------------------
            # TTS WORKER
            # ------------------------------------------------

            self._worker = TTSWorker(
                provider=self._provider,
                logger=self.logger,
            )

            self._worker.start()

            # ------------------------------------------------
            # SPEECH QUEUE
            # ------------------------------------------------

            self._queue = SpeechQueue(
                player=self._player,
                logger=self.logger,
            )

            self._queue.start()

            self._initialized = True

            self._log(
                "SpeechController initialized."
            )

        except Exception as exc:

            self._log(
                f"SpeechController initialization failed: {exc}",
                error=True,
            )

            self.shutdown()

            raise

    # ======================================================
    # SPEAK
    # ======================================================

    def speak(
        self,
        text: str,
    ) -> Optional[int]:
        """
        Queue text for speech synthesis.

        Returns:
            Sequence number assigned by TTSWorker.
        """

        if not text or not text.strip():
            return None

        if not self._initialized:
            self.initialize()

        if self._worker is None:
            raise RuntimeError(
                "TTS worker is unavailable."
            )

        text = text.strip()

        self._log(
            f"Speech requested: {text[:100]!r}"
        )

        sequence = self._worker.submit(
            text
        )

        return sequence

    # ======================================================
    # STOP
    # ======================================================

    def stop(self) -> None:
        """
        Stop current playback and clear pending speech.
        """

        self._log(
            "Stopping speech."
        )

        if self._queue is not None:

            try:
                self._queue.stop()
            except Exception as exc:

                self._log(
                    f"Failed to stop speech queue: {exc}",
                    error=True,
                )

        if self._player is not None:

            try:
                self._player.stop()
            except Exception as exc:

                self._log(
                    f"Failed to stop audio player: {exc}",
                    error=True,
                )

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def is_initialized(self) -> bool:
        """
        Whether the speech subsystem is initialized.
        """

        return self._initialized

    @property
    def is_speaking(self) -> bool:
        """
        Whether audio is currently being played.
        """

        if self._player is None:
            return False

        return self._player.is_playing

    @property
    def pending(self) -> int:
        """
        Number of speech items waiting for playback.

        Returns zero when the subsystem is not initialized.
        """

        if self._queue is None:
            return 0

        return self._queue.pending

    # ======================================================
    # SHUTDOWN
    # ======================================================

    def shutdown(self) -> None:
        """
        Shut down the complete speech subsystem.
        """

        self._log(
            "Shutting down SpeechController..."
        )

        # --------------------------------------------------
        # Stop playback first.
        # --------------------------------------------------

        if self._player is not None:

            try:
                self._player.stop()
            except Exception as exc:

                self._log(
                    f"AudioPlayer shutdown error: {exc}",
                    error=True,
                )

        # --------------------------------------------------
        # Stop speech queue.
        # --------------------------------------------------

        if self._queue is not None:

            try:
                self._queue.stop()
            except Exception as exc:

                self._log(
                    f"SpeechQueue shutdown error: {exc}",
                    error=True,
                )

        # --------------------------------------------------
        # Stop TTS worker.
        # --------------------------------------------------

        if self._worker is not None:

            try:
                self._worker.stop()
            except Exception as exc:

                self._log(
                    f"TTSWorker shutdown error: {exc}",
                    error=True,
                )

        # --------------------------------------------------
        # Release Kokoro.
        # --------------------------------------------------

        if self._provider is not None:

            try:
                self._provider.shutdown()
            except Exception as exc:

                self._log(
                    f"Kokoro shutdown error: {exc}",
                    error=True,
                )

        self._provider = None
        self._player = None
        self._worker = None
        self._queue = None

        self._initialized = False

        self._log(
            "SpeechController shutdown complete."
        )

    # ======================================================
    # LOGGING
    # ======================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:
        """
        Safely write to Krakken's logger.
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

