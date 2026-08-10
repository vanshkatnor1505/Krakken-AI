
"""
Krakken AI — LLM Provider Interface.

Defines the contract that every Krakken language-model
provider must implement.

Architecture:

    User Input
         ↓
    Assistant
         ↓
    LLMProvider
         ↓
    Final Response
         ↓
    ResponseHandler

This module intentionally knows nothing about:

- Speech
- Kokoro
- Audio
- UI
- Conversation rendering
- Specific LLM vendors
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """
    Abstract interface for Krakken's language-model providers.

    Concrete implementations may connect to:

    - Local models
    - Ollama
    - OpenAI
    - Gemini
    - Anthropic
    - Other future providers

    The Assistant should only depend on this interface.
    """

    def __init__(
        self,
        *,
        logger: Any = None,
    ) -> None:

        self.logger = logger

    # ==================================================
    # GENERATE
    # ==================================================

    @abstractmethod
    def generate(
        self,
        prompt: str,
    ) -> str:
        """
        Generate a response from the language model.

        Args:
            prompt:
                User input or formatted model prompt.

        Returns:
            Final assistant response as text.

        Raises:
            Exception:
                Implementations should raise when generation
                fails rather than silently returning invalid data.
        """

        raise NotImplementedError

    # ==================================================
    # INITIALIZATION
    # ==================================================

    def initialize(self) -> None:
        """
        Initialize the provider.

        Providers that require initialization should
        override this method.

        Providers that do not require initialization may
        leave the default implementation unchanged.
        """

        return None

    # ==================================================
    # STATUS
    # ==================================================

    @property
    def is_initialized(self) -> bool:
        """
        Return whether the provider is initialized.

        The default implementation assumes providers that
        do not require initialization are always ready.
        """

        return True

    # ==================================================
    # SHUTDOWN
    # ==================================================

    def shutdown(self) -> None:
        """
        Release provider resources.

        Providers with no resources may leave the default
        implementation unchanged.
        """

        return None

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
            # Logging must never break the assistant.
            pass

