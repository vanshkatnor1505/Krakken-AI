
"""
AI provider abstraction for Krakken AI.

The application communicates with AI providers through this module
instead of coupling the rest of the application directly to
Groq's SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any

from core.ai.models import AIChunk, AIResponse, ChatMessage


class AIProviderError(Exception):
    """
    Base exception for AI provider failures.
    """


class AIProvider(ABC):
    """
    Abstract interface for AI providers.
    """

    @abstractmethod
    def chat(
        self,
        messages: Sequence[ChatMessage],
    ) -> AIResponse:
        """
        Execute a normal, non-streaming chat request.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: Sequence[ChatMessage],
    ) -> Iterator[AIChunk]:
        """
        Execute a streaming chat request.
        """
        raise NotImplementedError


class GroqProvider(AIProvider):
    """
    Groq implementation of the Krakken AI provider.

    Configuration comes from AppConfig:

        config.groq_api_key
        config.groq_model
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        logger: Any = None,
    ) -> None:

        if not api_key:
            raise AIProviderError(
                "GROQ_API_KEY is not configured."
            )

        if not model:
            raise AIProviderError(
                "GROQ_MODEL is not configured."
            )

        try:
            from groq import Groq

        except ImportError as exc:
            raise AIProviderError(
                "Groq SDK is not installed. "
                "Run: pip install groq"
            ) from exc

        self._client = Groq(
            api_key=api_key,
        )

        self._model = model
        self._logger = logger

        self._log(
            f"Groq provider initialized with model: {model}"
        )

    # ==========================================================
    # NORMAL CHAT
    # ==========================================================

    def chat(
        self,
        messages: Sequence[ChatMessage],
    ) -> AIResponse:

        self._validate_messages(messages)

        payload = [
            message.to_dict()
            for message in messages
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=payload,
            )

        except Exception as exc:
            self._raise_provider_error(exc)

        try:
            if not response.choices:
                raise AIProviderError(
                    "Groq returned no choices."
                )

            choice = response.choices[0]

            content = (
                choice.message.content
                or ""
            )

            finish_reason = getattr(
                choice,
                "finish_reason",
                None,
            )

            usage_data = getattr(
                response,
                "usage",
                None,
            )

            usage: dict[str, int] = {}

            if usage_data:

                prompt_tokens = getattr(
                    usage_data,
                    "prompt_tokens",
                    None,
                )

                completion_tokens = getattr(
                    usage_data,
                    "completion_tokens",
                    None,
                )

                total_tokens = getattr(
                    usage_data,
                    "total_tokens",
                    None,
                )

                if prompt_tokens is not None:
                    usage["prompt_tokens"] = prompt_tokens

                if completion_tokens is not None:
                    usage["completion_tokens"] = completion_tokens

                if total_tokens is not None:
                    usage["total_tokens"] = total_tokens

            return AIResponse(
                content=content,
                model=self._model,
                finish_reason=finish_reason,
                usage=usage,
            )

        except AIProviderError:
            raise

        except Exception as exc:
            raise AIProviderError(
                f"Invalid response from Groq: {exc}"
            ) from exc

    # ==========================================================
    # STREAMING CHAT
    # ==========================================================

    def stream(
        self,
        messages: Sequence[ChatMessage],
    ) -> Iterator[AIChunk]:

        self._validate_messages(messages)

        payload = [
            message.to_dict()
            for message in messages
        ]

        try:

            response_stream = (
                self._client.chat.completions.create(
                    model=self._model,
                    messages=payload,
                    stream=True,
                )
            )

            finished = False

            for chunk in response_stream:

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                delta = getattr(
                    choice,
                    "delta",
                    None,
                )

                if delta is None:
                    continue

                content = getattr(
                    delta,
                    "content",
                    None,
                )

                finish_reason = getattr(
                    choice,
                    "finish_reason",
                    None,
                )

                # --------------------------------------------------
                # Content must ALWAYS be delivered before finished.
                # --------------------------------------------------

                if content:

                    yield AIChunk(
                        content=content,
                        finished=False,
                        finish_reason=None,
                    )

                # --------------------------------------------------
                # Groq signals completion with finish_reason.
                # --------------------------------------------------

                if finish_reason:

                    finished = True

                    yield AIChunk(
                        content="",
                        finished=True,
                        finish_reason=finish_reason,
                    )

                    break

            # ------------------------------------------------------
            # Safety fallback.
            #
            # Some provider implementations may close the stream
            # without providing a finish_reason.
            # ------------------------------------------------------

            if not finished:

                yield AIChunk(
                    content="",
                    finished=True,
                    finish_reason="stop",
                )

        except AIProviderError:
            raise

        except Exception as exc:
            self._raise_provider_error(exc)

    # ==========================================================
    # VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_messages(
        messages: Sequence[ChatMessage],
    ) -> None:

        if not messages:

            raise AIProviderError(
                "At least one chat message is required."
            )

        for message in messages:

            if not isinstance(
                message,
                ChatMessage,
            ):
                raise AIProviderError(
                    "All messages must be ChatMessage objects."
                )

            if not message.content.strip():

                raise AIProviderError(
                    "Chat messages cannot contain empty content."
                )

    # ==========================================================
    # ERROR HANDLING
    # ==========================================================

    def _raise_provider_error(
        self,
        exc: Exception,
    ) -> None:

        # Never include the API key in an exception/log message.
        message = str(exc)

        self._log(
            f"Groq request failed: {message}",
            error=True,
        )

        raise AIProviderError(
            f"Groq request failed: {message}"
        ) from exc

    # ==========================================================
    # LOGGING
    # ==========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:

        if self._logger is None:
            return

        try:

            if error:
                self._logger.error(message)

            else:
                self._logger.info(message)

        except Exception:
            # Logging must never crash the provider.
            pass

