"""
Krakken AI - Voice Input Service.

Records microphone audio and transcribes it with Groq speech-to-text.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np


class VoiceInputServiceError(Exception):
    """Raised when microphone capture or transcription fails."""


class VoiceInputService:
    """
    Records a short microphone capture and transcribes it.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
        language: str = "en",
        sample_rate: int = 16000,
        channels: int = 1,
        logger: Any = None,
    ) -> None:

        self._api_key = api_key
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._channels = channels
        self._logger = logger

        self._client = None
        self._stream = None
        self._lock = threading.RLock()
        self._frames: list[np.ndarray] = []
        self._recording_path: Path | None = None
        self._recording = False

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        if not self._api_key:
            raise VoiceInputServiceError(
                "GROQ_API_KEY is not configured."
            )

        try:
            from groq import Groq
        except ImportError as exc:
            raise VoiceInputServiceError(
                "Groq SDK is not installed."
            ) from exc

        self._client = Groq(api_key=self._api_key)

    # ======================================================
    # RECORDING
    # ======================================================

    def start_recording(self) -> None:
        if self.is_recording:
            return

        self._ensure_client()

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise VoiceInputServiceError(
                "sounddevice is not installed."
            ) from exc

        with self._lock:
            self._frames = []
            self._recording_path = None

            def _callback(indata, frames, time, status):  # noqa: ANN001
                if status:
                    self._log(f"Mic status: {status}")
                with self._lock:
                    if self._recording:
                        self._frames.append(indata.copy())

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                callback=_callback,
            )
            self._stream.start()
            self._recording = True

        self._log("Voice recording started.")

    def stop_recording(self) -> Path | None:
        if not self.is_recording:
            return None

        try:
            import soundfile as sf
        except ImportError as exc:
            raise VoiceInputServiceError(
                "soundfile is not installed."
            ) from exc

        with self._lock:
            stream = self._stream
            self._stream = None
            self._recording = False
            frames = list(self._frames)
            self._frames = []

        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

        if not frames:
            self._log("No microphone frames captured.")
            return None

        audio = np.concatenate(frames, axis=0)

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )
        temp_file.close()

        path = Path(temp_file.name)

        sf.write(
            str(path),
            audio,
            self._sample_rate,
            subtype="PCM_16",
        )

        with self._lock:
            self._recording_path = path

        self._log(f"Voice recording stopped: {path}")
        return path

    # ======================================================
    # TRANSCRIPTION
    # ======================================================

    def transcribe_file(
        self,
        path: str | Path,
        *,
        prompt: str | None = None,
    ) -> str:
        self._ensure_client()

        audio_path = Path(path)

        if not audio_path.exists():
            raise VoiceInputServiceError(
                f"Audio file not found: {audio_path}"
            )

        try:
            with audio_path.open("rb") as file:
                transcription = (
                    self._client.audio.transcriptions.create(
                        file=(audio_path.name, file.read()),
                        model=self._model,
                        prompt=prompt,
                        response_format="json",
                        language=self._language,
                        temperature=0.0,
                    )
                )

            text = getattr(transcription, "text", "") or ""
            text = text.strip()

            self._log(
                f"Transcription completed: {text[:120]!r}"
            )

            return text

        except Exception as exc:
            raise VoiceInputServiceError(
                f"Speech-to-text failed: {exc}"
            ) from exc

    def capture_and_transcribe(
        self,
        *,
        prompt: str | None = None,
    ) -> str:
        path = self.stop_recording()

        if path is None:
            return ""

        try:
            return self.transcribe_file(
                path,
                prompt=prompt,
            )
        finally:
            self.cleanup(path)

    # ======================================================
    # CLEANUP
    # ======================================================

    def cleanup(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else None

        if target is None:
            with self._lock:
                target = self._recording_path
                self._recording_path = None

        if target is None:
            return

        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    # ======================================================
    # LOGGING
    # ======================================================

    def _log(self, message: str, error: bool = False) -> None:
        if self._logger is None:
            return

        try:
            if error:
                self._logger.error(message)
            else:
                self._logger.info(message)
        except Exception:
            pass
