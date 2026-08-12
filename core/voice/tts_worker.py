"""
Krakken AI - TTS Worker.

Background worker responsible for converting text into AudioData.

Architecture:

    Text Queue
         ↓
    TTS Worker
         ↓
    TTS Provider
         ↓
    Audio Queue
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Optional

from core.voice.tts_provider import TTSProvider, AudioData


@dataclass(slots=True)
class SpeechTask:
    """
    One piece of text waiting for synthesis.
    """

    text: str
    sequence: int


class TTSWorker:
    """
    Background text-to-speech generation worker.
    """

    def __init__(
        self,
        provider: TTSProvider,
        logger: Any = None,
    ) -> None:

        if provider is None:
            raise ValueError(
                "TTS provider cannot be None."
            )

        self.provider = provider
        self.logger = logger

        self._tasks: queue.Queue[
            Optional[SpeechTask]
        ] = queue.Queue()

        self._audio: queue.Queue[
            tuple[int, AudioData]
        ] = queue.Queue()

        self._thread: Optional[
            threading.Thread
        ] = None

        self._running = False
        self._stop_event = threading.Event()

        self._sequence = 0

        self._log(
            "TTSWorker created."
        )

    # ==================================================
    # START
    # ==================================================

    def start(self) -> None:
        """
        Start the background worker.
        """

        if self._running:
            return

        self._stop_event.clear()

        self._running = True

        self._thread = threading.Thread(
            target=self._run,
            name="Krakken-TTS-Worker",
            daemon=True,
        )

        self._thread.start()

        self._log(
            "TTS worker started."
        )

    # ==================================================
    # SUBMIT
    # ==================================================

    def submit(
        self,
        text: str,
    ) -> int:
        """
        Submit text for background synthesis.

        Returns:
            Sequence number assigned to the task.
        """

        if not text or not text.strip():
            raise ValueError(
                "Cannot submit empty speech."
            )

        if not self._running:
            self.start()

        text = text.strip()

        sequence = self._sequence

        self._sequence += 1

        task = SpeechTask(
            text=text,
            sequence=sequence,
        )

        self._tasks.put(task)

        self._log(
            f"TTS task queued [{sequence}]: "
            f"{text[:80]!r}"
        )

        return sequence

    # ==================================================
    # WORKER
    # ==================================================

    def _run(self) -> None:
        """
        Main TTS worker loop.
        """

        while not self._stop_event.is_set():

            try:

                task = self._tasks.get(
                    timeout=0.1
                )

            except queue.Empty:

                continue

            if task is None:

                self._tasks.task_done()

                break

            try:

                self._log(
                    f"Synthesizing [{task.sequence}]"
                )

                audio = self.provider.synthesize(
                    task.text
                )

                if audio is None:

                    self._log(
                        f"No audio returned for "
                        f"[{task.sequence}]",
                        error=True,
                    )

                    continue

                if self._stop_event.is_set():

                    continue

                self._audio.put(
                    (
                        task.sequence,
                        audio,
                    )
                )

                self._log(
                    f"Audio ready [{task.sequence}]"
                )

            except Exception as exc:

                self._log(
                    f"TTS synthesis failed "
                    f"[{task.sequence}]: {exc}",
                    error=True,
                )

            finally:

                self._tasks.task_done()

        self._running = False

        self._log(
            "TTS worker stopped."
        )

    # ==================================================
    # AUDIO
    # ==================================================

    def get_audio(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[tuple[int, AudioData]]:
        """
        Retrieve synthesized audio.

        Returns:
            (sequence, AudioData)
            or None if no audio is available.
        """

        try:

            return self._audio.get(
                timeout=timeout
            )

        except queue.Empty:

            return None

    # ==================================================
    # STOP
    # ==================================================

    def stop(self) -> None:
        """
        Stop the worker and clear pending work.
        """

        self._log(
            "Stopping TTS worker."
        )

        self._stop_event.set()

        # Wake the worker.

        self._tasks.put(None)

        # Clear pending text.

        while True:

            try:

                self._tasks.get_nowait()
                self._tasks.task_done()

            except queue.Empty:

                break

        # Clear generated audio.

        while True:

            try:

                self._audio.get_nowait()
                self._audio.task_done()

            except queue.Empty:

                break

        self._running = False

        self._log(
            "TTS worker stopped."
        )

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def pending_tasks(self) -> int:
        return self._tasks.qsize()

    @property
    def pending_audio(self) -> int:
        return self._audio.qsize()

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