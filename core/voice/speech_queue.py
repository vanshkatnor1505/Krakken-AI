"""
Krakken AI - Speech Queue.

Consumes synthesized AudioData in sequence and sends
it to the AudioPlayer.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Optional

from core.voice.tts_provider import AudioData
from core.voice.audio_player import AudioPlayer


class SpeechQueue:
    """
    Ordered audio playback queue.
    """

    def __init__(
        self,
        player: AudioPlayer,
        logger: Any = None,
    ) -> None:

        if player is None:
            raise ValueError(
                "AudioPlayer cannot be None."
            )

        self.player = player
        self.logger = logger

        self._queue: queue.Queue[
            Optional[tuple[int, AudioData]]
        ] = queue.Queue()

        self._thread: Optional[
            threading.Thread
        ] = None

        self._running = False
        self._stop_event = threading.Event()

    # ==================================================
    # START
    # ==================================================

    def start(self) -> None:

        if self._running:
            return

        self._stop_event.clear()

        self._running = True

        self._thread = threading.Thread(
            target=self._run,
            name="Krakken-Speech-Playback",
            daemon=True,
        )

        self._thread.start()

        self._log(
            "Speech queue started."
        )

    # ==================================================
    # SUBMIT
    # ==================================================

    def submit(
        self,
        sequence: int,
        audio: AudioData,
    ) -> None:

        if audio is None:
            return

        if not self._running:
            self.start()

        self._queue.put(
            (
                sequence,
                audio,
            )
        )

        self._log(
            f"Audio queued for playback [{sequence}]"
        )

    # ==================================================
    # PLAYBACK
    # ==================================================

    def _run(self) -> None:

        while not self._stop_event.is_set():

            try:

                item = self._queue.get(
                    timeout=0.1
                )

            except queue.Empty:

                continue

            if item is None:

                self._queue.task_done()

                break

            sequence, audio = item

            try:

                self._log(
                    f"Playing audio [{sequence}]"
                )

                self.player.play(
                    audio,
                    blocking=True,
                )

            except Exception as exc:

                self._log(
                    f"Playback failed "
                    f"[{sequence}]: {exc}",
                    error=True,
                )

            finally:

                self._queue.task_done()

        self._running = False

        self._log(
            "Speech queue stopped."
        )

    # ==================================================
    # STOP
    # ==================================================

    def stop(self) -> None:

        self._stop_event.set()

        self._queue.put(None)

        try:
            self.player.stop()
        except Exception:
            pass

        while True:

            try:

                self._queue.get_nowait()
                self._queue.task_done()

            except queue.Empty:

                break

        self._running = False

        self._log(
            "Speech queue stopped."
        )

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_playing(self) -> bool:

        return self.player.is_playing

    @property
    def pending(self) -> int:

        return self._queue.qsize()

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
                self.logger.error(message)
            else:
                self.logger.info(message)

        except Exception:
            pass