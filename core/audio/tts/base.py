"""
Krakken AI - Text-to-Speech Provider Interface.

Defines the common interface used by all TTS providers.

The rest of Krakken should never depend directly on a
specific TTS engine such as Kokoro, Piper, or a cloud API.

Architecture:

    VoiceService
         ↓
    TTSProvider
         ↓
    ┌───────────────┬───────────────┐
    │               │               │
    Kokoro        Piper         Cloud TTS
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TTSResult:
    """
    Result returned by a TTS provider.

    Attributes:
        audio:
            Generated audio data.

        sample_rate:
            Audio sample rate in Hz.

        channels:
            Number of audio channels.

        sample_width:
            Number of bytes per audio sample.

        metadata:
            Optional provider-specific information.
    """

    audio: bytes

    sample_rate: int

    channels: int = 1

    sample_width: int = 2

    metadata: dict[str, Any] | None = None


class TTSProvider(ABC):
    """
    Abstract interface for a Krakken text-to-speech engine.

    Providers must implement synthesis while the rest of
    the application remains provider-independent.
    """

    # ======================================================
    # PROVIDER INFORMATION
    # ======================================================

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the human-readable provider name.
        """

        raise NotImplementedError

    @property
    @abstractmethod
    def voice(self) -> str:
        """
        Return the currently selected voice identifier.
        """

        raise NotImplementedError

    # ======================================================
    # AVAILABILITY
    # ======================================================

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True when the provider is ready for use.

        This should perform a lightweight availability check.
        """

        raise NotImplementedError

    # ======================================================
    # SYNTHESIS
    # ======================================================

    @abstractmethod
    def synthesize(
        self,
        text: str,
    ) -> TTSResult:
        """
        Convert text into audio.

        Args:
            text:
                Text that should be spoken.

        Returns:
            TTSResult containing the generated audio.

        Raises:
            RuntimeError:
                If synthesis cannot be completed.
        """

        raise NotImplementedError

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def initialize(self) -> None:
        """
        Initialize the provider.

        Providers that require model loading, device
        initialization, or other startup work can override this.

        The default implementation does nothing.
        """

    def shutdown(self) -> None:
        """
        Release provider resources.

        The default implementation does nothing.
        """

    # ======================================================
    # OPTIONAL CONTROLS
    # ======================================================

    def set_voice(
        self,
        voice: str,
    ) -> None:
        """
        Change the active voice.

        Providers that support multiple voices should override
        this method.
        """

        raise NotImplementedError(
            f"{self.name} does not support voice selection."
        )

    def set_speed(
        self,
        speed: float,
    ) -> None:
        """
        Change speech speed.

        A value of 1.0 represents normal speed.

        Providers that support speed control should override
        this method.
        """

        raise NotImplementedError(
            f"{self.name} does not support speed control."
        )

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"voice={self.voice!r}"
            f")"
        )