"""
Krakken AI - Audio Player.

Responsible only for playing generated audio.

Architecture:

    TTS Provider
         ↓
      AudioData
         ↓
     AudioPlayer
         ↓
    System Output

The player intentionally knows nothing about:

- AI responses
- Kokoro
- EventBus
- QML
- speech selection
"""

from __future__ import annotations

from threading import RLock
from typing import Any

import numpy as np
import sounddevice as sd

from core.voice.tts_provider import AudioData


class AudioPlayer:
    """
    Plays generated audio through the system audio device.

    The player supports both blocking and non-blocking playback.

    Blocking playback is useful for sequential TTS queues.

    Non-blocking playback is useful when the caller manages
    playback state independently.
    """

    def __init__(
        self,
        logger: Any = None,
    ) -> None:

        self.logger = logger

        self._playing = False

        self._lock = RLock()

        self._log(
            "AudioPlayer initialized."
        )

    # ==========================================================
    # PLAY
    # ==========================================================

    def play(
        self,
        audio: AudioData,
        *,
        blocking: bool = True,
    ) -> None:
        """
        Play an AudioData object.

        Args:
            audio:
                Generated audio.

            blocking:
                If True, wait until playback finishes.

                If False, return immediately after playback
                starts.
        """

        if audio is None:
            raise ValueError(
                "AudioData cannot be None."
            )

        if audio.samples is None:
            raise ValueError(
                "Audio samples cannot be None."
            )

        if audio.sample_rate <= 0:
            raise ValueError(
                "Invalid sample rate."
            )

        if audio.channels <= 0:
            raise ValueError(
                "Invalid channel count."
            )

        if audio.sample_width <= 0:
            raise ValueError(
                "Invalid sample width."
            )

        # ------------------------------------------------------
        # Decode samples
        # ------------------------------------------------------

        samples = self._decode_samples(
            audio
        )

        if samples.size == 0:

            self._log(
                "AudioPlayer received empty audio."
            )

            return

        # ------------------------------------------------------
        # Normalize channels
        # ------------------------------------------------------

        samples = self._normalize_channels(
            samples,
            audio.channels,
        )

        duration = (
            samples.shape[0]
            / audio.sample_rate
        )

        self._log(
            "Starting audio playback."
        )

        self._log(
            f"Sample rate: {audio.sample_rate}"
        )

        self._log(
            f"Channels: {audio.channels}"
        )

        self._log(
            f"NumPy dtype: {samples.dtype}"
        )

        self._log(
            f"Samples: {samples.size}"
        )

        self._log(
            f"Duration: {duration:.2f}s"
        )

        # ------------------------------------------------------
        # Playback
        # ------------------------------------------------------

        try:

            with self._lock:

                self._playing = True

            sd.play(
                samples,
                samplerate=audio.sample_rate,
                blocking=blocking,
            )

            if blocking:

                self._log(
                    "Audio playback completed."
                )

            else:

                self._log(
                    "Audio playback started."
                )

        except Exception as exc:

            with self._lock:

                self._playing = False

            self._log(
                f"Audio playback failed: {exc}",
                error=True,
            )

            raise

        finally:

            if blocking:

                with self._lock:

                    self._playing = False

    # ==========================================================
    # DECODE
    # ==========================================================

    def _decode_samples(
        self,
        audio: AudioData,
    ) -> np.ndarray:
        """
        Convert AudioData samples into a NumPy array
        compatible with sounddevice.
        """

        samples = audio.samples

        # ------------------------------------------------------
        # NumPy
        # ------------------------------------------------------

        if isinstance(
            samples,
            np.ndarray,
        ):

            array = samples

            if array.size == 0:

                return array

            if np.issubdtype(
                array.dtype,
                np.integer,
            ):

                if array.dtype != np.int16:

                    array = array.astype(
                        np.int16
                    )

            elif np.issubdtype(
                array.dtype,
                np.floating,
            ):

                array = array.astype(
                    np.float32
                )

            else:

                raise TypeError(
                    "Unsupported NumPy audio dtype: "
                    f"{array.dtype}"
                )

            return array

        # ------------------------------------------------------
        # Raw bytes
        # ------------------------------------------------------

        if isinstance(
            samples,
            (
                bytes,
                bytearray,
                memoryview,
            ),
        ):

            raw = bytes(
                samples
            )

            if not raw:

                return np.empty(
                    0,
                    dtype=np.int16,
                )

            # --------------------------------------------------
            # 8-bit PCM
            # --------------------------------------------------

            if audio.sample_width == 1:

                return np.frombuffer(
                    raw,
                    dtype=np.uint8,
                )

            # --------------------------------------------------
            # 16-bit PCM
            # --------------------------------------------------

            if audio.sample_width == 2:

                if len(raw) % 2 != 0:

                    raise ValueError(
                        "Invalid PCM16 data."
                    )

                return np.frombuffer(
                    raw,
                    dtype="<i2",
                )

            # --------------------------------------------------
            # 32-bit PCM
            # --------------------------------------------------

            if audio.sample_width == 4:

                if len(raw) % 4 != 0:

                    raise ValueError(
                        "Invalid PCM32 data."
                    )

                return np.frombuffer(
                    raw,
                    dtype="<i4",
                )

            raise ValueError(
                "Unsupported PCM sample width: "
                f"{audio.sample_width} bytes."
            )

        raise TypeError(
            "Unsupported audio sample type: "
            f"{type(samples).__name__}"
        )

    # ==========================================================
    # CHANNELS
    # ==========================================================

    def _normalize_channels(
        self,
        samples: np.ndarray,
        channels: int,
    ) -> np.ndarray:
        """
        Normalize audio into the shape expected by sounddevice.
        """

        if channels == 1:

            return samples.reshape(-1)

        total_samples = samples.size

        if total_samples % channels != 0:

            raise ValueError(
                "Audio sample count "
                f"{total_samples} cannot be divided "
                f"into {channels} channels."
            )

        return samples.reshape(
            -1,
            channels,
        )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(self) -> None:
        """
        Immediately stop current playback.
        """

        try:

            sd.stop()

            with self._lock:

                self._playing = False

            self._log(
                "Audio playback stopped."
            )

        except Exception as exc:

            self._log(
                f"Failed to stop audio: {exc}",
                error=True,
            )

    # ==========================================================
    # STATUS
    # ==========================================================

    @property
    def is_playing(self) -> bool:

        with self._lock:

            return self._playing

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