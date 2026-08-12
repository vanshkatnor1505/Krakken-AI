"""
Krakken AI - Streaming Speech Engine.

Converts streaming AI text into speech as sentences become available.

Architecture:

    AI Response Chunks
            ↓
       SpeechStream
            ↓
      Sentence Buffer
            ↓
       TTS Provider
            ↓
        Audio Queue
            ↓
        AudioPlayer

The engine does not know anything about:
- QML
- AI models
- microphones
- conversation state
"""

from __future__ import annotations

import queue
import re
import threading
from typing import Optional, Any

from core.voice.tts_provider import TTSProvider, AudioData
from core.voice.audio_player import AudioPlayer


class SpeechStream:
    """
    Sentence-aware streaming TTS engine.
    """

    def __init__(
        self,
        tts_provider: TTSProvider,
        audio_player: AudioPlayer,
        logger: Any = None,
    ) -> None:

        if tts_provider is None:
            raise ValueError(
                "tts_provider cannot be None."
            )

        if audio_player is None:
            raise ValueError(
                "audio_player cannot be None."
            )

        self.tts_provider = tts_provider
        self.audio_player = audio_player
        self.logger = logger

        self._buffer = ""

        self._queue: queue.Queue[Optional[AudioData]] = (
            queue.Queue()
        )

        self._worker: Optional[threading.Thread] = None

        self._running = False
        self._stopped = False

        self._lock = threading.Lock()

        self._log(
            "SpeechStream initialized."
        )

    # ==================================================
    # START
    # ==================================================

    def start(self) -> None:
        """
        Start a new streaming speech session.
        """

        with self._lock:

            if self._running:
                return

            self._running = True
            self._stopped = False
            self._buffer = ""

        self._log(
            "Speech stream started."
        )

        self._worker = threading.Thread(
            target=self._playback_worker,
            name="Krakken-Speech-Worker",
            daemon=True,
        )

        self._worker.start()

    # ==================================================
    # FEED
    # ==================================================

    def feed(self, text: str) -> None:
        """
        Feed a new chunk of AI-generated text.

        The chunk may contain:
        - partial words
        - multiple words
        - complete sentences
        - multiple sentences
        """

        if not text:
            return

        with self._lock:

            if not self._running:
                self.start()

            self._buffer += text

        self._process_buffer()

    # ==================================================
    # BUFFER PROCESSING
    # ==================================================

    def _process_buffer(self) -> None:
        """
        Extract complete sentences from the buffer.
        """

        while True:

            sentence = self._extract_sentence()

            if sentence is None:
                break

            sentence = sentence.strip()

            if not sentence:
                continue

            self._log(
                f"Sentence ready: {sentence!r}"
            )

            self._synthesize_sentence(
                sentence
            )

    # ==================================================
    # SENTENCE EXTRACTION
    # ==================================================

    def _extract_sentence(self) -> Optional[str]:
        """
        Extract the first complete sentence.

        Supports:
            .
            !
            ?
            newline

        Avoids splitting common decimal numbers.
        """

        if not self._buffer:
            return None

        text = self._buffer

        # ----------------------------------------------
        # Sentence-ending punctuation.
        # ----------------------------------------------

        match = re.search(
            r"(?<=[.!?])(?:[\"'”’)\]]*)\s+",
            text,
        )

        if match:

            end = match.end()

            sentence = text[:end]

            self._buffer = text[end:]

            return sentence

        # ----------------------------------------------
        # Explicit newline.
        # ----------------------------------------------

        newline_index = text.find("\n")

        if newline_index >= 0:

            sentence = text[:newline_index]

            self._buffer = text[
                newline_index + 1:
            ]

            if sentence.strip():
                return sentence

        return None

    # ==================================================
    # SYNTHESIS
    # ==================================================

    def _synthesize_sentence(
        self,
        sentence: str,
    ) -> None:

        if self._stopped:
            return

        try:

            audio = self.tts_provider.synthesize(
                sentence
            )

            if audio is None:
                self._log(
                    "TTS provider returned no audio.",
                    error=True,
                )

                return

            if self._stopped:
                return

            self._queue.put(
                audio
            )

            self._log(
                "Audio queued."
            )

        except Exception as exc:

            self._log(
                f"Sentence synthesis failed: {exc}",
                error=True,
            )

    # ==================================================
    # FINISH
    # ==================================================

    def finish(self) -> None:
        """
        Finish the current response.

        Any remaining text in the buffer is synthesized.
        """

        with self._lock:

            if not self._running:
                return

            remaining = self._buffer.strip()

            self._buffer = ""

        if remaining:

            self._log(
                f"Final text: {remaining!r}"
            )

            self._synthesize_sentence(
                remaining
            )

        # Sentinel tells playback worker that
        # no more audio will be added.

        self._queue.put(None)

        self._log(
            "Speech stream finished."
        )

    # ==================================================
    # PLAYBACK WORKER
    # ==================================================

    def _playback_worker(self) -> None:
        """
        Sequentially play generated audio.
        """

        while True:

            try:

                audio = self._queue.get()

            except Exception:
                break

            # ------------------------------------------
            # None = end of stream.
            # ------------------------------------------

            if audio is None:

                break

            if self._stopped:
                break

            try:

                self._log(
                    "Playing queued audio."
                )

                self.audio_player.play(
                    audio,
                    blocking=True,
                )

            except Exception as exc:

                self._log(
                    f"Audio playback failed: {exc}",
                    error=True,
                )

            finally:

                self._queue.task_done()

        with self._lock:

            self._running = False

        self._log(
            "Speech playback worker finished."
        )

    # ==================================================
    # STOP
    # ==================================================

    def stop(self) -> None:
        """
        Immediately stop speech generation/playback.
        """

        self._log(
            "Stopping speech stream."
        )

        self._stopped = True

        with self._lock:

            self._buffer = ""
            self._running = False

        # Stop current audio.

        try:

            self.audio_player.stop()

        except Exception as exc:

            self._log(
                f"Failed to stop audio: {exc}",
                error=True,
            )

        # Empty pending audio.

        while True:

            try:

                item = self._queue.get_nowait()

                if item is not None:
                    self._queue.task_done()

            except queue.Empty:

                break

        self._log(
            "Speech stream stopped."
        )

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_running(self) -> bool:

        return self._running

    # ==================================================
    # LOGGING
    # ==================================================

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