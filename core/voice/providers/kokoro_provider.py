
"""
Krakken AI - Kokoro TTS Provider.

Local text-to-speech implementation using Kokoro.

Responsibilities:

    Text
      ↓
    Kokoro
      ↓
    NumPy audio
      ↓
    AudioData

This class does NOT:

- play audio
- manage audio devices
- manage playback queues
- interact with QML
- control assistant state
"""

from __future__ import annotations

from typing import Any

from core.voice.tts_provider import AudioData, TTSProvider


class KokoroProvider(TTSProvider):
    """
    Kokoro-based local TTS provider.
    """

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.0,
        logger: Any = None,
    ) -> None:

        self.voice = voice
        self.speed = speed
        self.logger = logger

        self._pipeline = None
        self._initialized = False
        self._device = "cpu"

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def initialize(self) -> None:
        """
        Load the Kokoro pipeline once.

        Automatically uses CUDA when an NVIDIA GPU is available.
        Falls back to CPU when CUDA is unavailable.
        """

        if self._initialized:
            return

        self._log(
            "Initializing Kokoro TTS..."
        )

        try:

            import torch
            from kokoro import KPipeline

            # --------------------------------------------------
            # Select execution device
            # --------------------------------------------------

            if torch.cuda.is_available():

                self._device = "cuda"

                self._log(
                    "CUDA is available."
                )

                self._log(
                    f"GPU detected: "
                    f"{torch.cuda.get_device_name(0)}"
                )

                self._log(
                    f"CUDA version: "
                    f"{torch.version.cuda}"
                )

            else:

                self._device = "cpu"

                self._log(
                    "CUDA is not available. "
                    "Falling back to CPU."
                )

            # --------------------------------------------------
            # Initialize Kokoro
            # --------------------------------------------------

            self._log(
                f"Kokoro execution device: "
                f"{self._device}"
            )

            self._pipeline = KPipeline(
                lang_code="a",
                device=self._device,
            )

            self._initialized = True

            self._log(
                f"Kokoro TTS initialized. "
                f"Voice: {self.voice}, "
                f"Device: {self._device}"
            )

        except Exception as exc:

            self._pipeline = None
            self._initialized = False

            self._log(
                f"Failed to initialize Kokoro: {exc}",
                error=True,
            )

            raise

    # ==========================================================
    # SYNTHESIS
    # ==========================================================

    def synthesize(
        self,
        text: str,
    ) -> AudioData:
        """
        Generate speech from text.
        """

        if not text or not text.strip():

            raise ValueError(
                "Cannot synthesize empty text."
            )

        if not self._initialized:

            self.initialize()

        if self._pipeline is None:

            raise RuntimeError(
                "Kokoro pipeline is not initialized."
            )

        text = text.strip()

        self._log(
            f"Synthesizing speech: "
            f"{text[:100]!r}"
        )

        try:

            generator = self._pipeline(
                text,
                voice=self.voice,
                speed=self.speed,
            )

            chunks = []

            for _, _, audio_chunk in generator:

                if audio_chunk is not None:

                    samples = self._audio_to_numpy(
                        audio_chunk
                    )

                    if samples.size > 0:

                        chunks.append(
                            samples
                        )

            if not chunks:

                raise RuntimeError(
                    "Kokoro returned no audio."
                )

            # --------------------------------------------------
            # Combine all generated chunks
            # --------------------------------------------------

            import numpy as np

            if len(chunks) == 1:

                samples = chunks[0]

            else:

                samples = np.concatenate(
                    chunks
                )

            samples = np.asarray(
                samples,
                dtype=np.float32,
            )

            samples = np.clip(
                samples,
                -1.0,
                1.0,
            )

            self._log(
                "Speech generated successfully. "
                f"Samples: {samples.size}"
            )

            return AudioData(
                samples=samples,
                sample_rate=24000,
                channels=1,
                sample_width=2,
            )

        except Exception as exc:

            self._log(
                f"Kokoro synthesis failed: {exc}",
                error=True,
            )

            raise

    # ==========================================================
    # AUDIO CONVERSION
    # ==========================================================

    @staticmethod
    def _audio_to_numpy(
        audio: Any,
    ):
        """
        Convert Kokoro output into float32 NumPy samples.

        Output:

            float32 samples approximately in [-1.0, 1.0]
        """

        try:

            import numpy as np

            # --------------------------------------------------
            # Torch Tensor
            # --------------------------------------------------

            if hasattr(audio, "detach"):

                audio = audio.detach()

            # --------------------------------------------------
            # Move tensor from GPU → CPU
            # --------------------------------------------------

            if hasattr(audio, "cpu"):

                audio = audio.cpu()

            # --------------------------------------------------
            # Convert tensor → NumPy
            # --------------------------------------------------

            if hasattr(audio, "numpy"):

                audio = audio.numpy()

            samples = np.asarray(
                audio,
                dtype=np.float32,
            )

            samples = np.squeeze(
                samples
            )

            samples = np.clip(
                samples,
                -1.0,
                1.0,
            )

            return samples

        except Exception as exc:

            raise RuntimeError(
                f"Failed to convert Kokoro audio: {exc}"
            ) from exc

    # ==========================================================
    # STATUS
    # ==========================================================

    @property
    def is_initialized(
        self,
    ) -> bool:

        return self._initialized

    @property
    def device(
        self,
    ) -> str:

        return self._device

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def shutdown(
        self,
    ) -> None:
        """
        Release Kokoro resources.
        """

        if not self._initialized:

            return

        self._log(
            "Shutting down Kokoro TTS..."
        )

        self._pipeline = None

        self._initialized = False

        self._device = "cpu"

        self._log(
            "Kokoro TTS shutdown complete."
        )

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
