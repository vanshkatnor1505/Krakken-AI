"""
AI provider abstraction for Krakken AI.

The application communicates with AI providers through this
module instead of coupling the rest of the application directly
to Groq's SDK.

Tool execution itself does NOT happen here.

The provider only:

    - sends messages to the AI provider
    - exposes tool definitions
    - receives AI responses
    - normalizes tool calls
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any

from core.ai.models import (
    AIChunk,
    AIResponse,
    AIToolCall,
    ChatMessage,
)
from core.tools.models import ToolDefinition

# ============================================================
# PROVIDER ERROR
# ============================================================


class AIProviderError(Exception):
    """
    Base exception for AI provider failures.
    """


# ============================================================
# PROVIDER INTERFACE
# ============================================================


class AIProvider(ABC):
    """
    Abstract interface for AI providers.
    """

    @abstractmethod
    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> AIResponse:
        """
        Execute a normal, non-streaming chat request.
        """

        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> Iterator[AIChunk]:
        """
        Execute a streaming chat request.
        """

        raise NotImplementedError


# ============================================================
# GROQ PROVIDER
# ============================================================


class GroqProvider(AIProvider):
    """
    Groq implementation of the Krakken AI provider.

    Provider-specific Groq SDK logic stays entirely inside this
    class.

    Tool execution is intentionally NOT handled here.
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
            api_key=api_key
        )

        self._model = model

        self._logger = logger

        self._log(
            f"Groq provider initialized with model: {model}"
        )

    # ========================================================
    # NORMAL CHAT
    # ========================================================

    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> AIResponse:

        self._validate_messages(
            messages
        )

        payload = [
            message.to_dict()
            for message in messages
        ]

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
        }

        tool_payload = (
            self._build_tool_payload(
                tools
            )
        )

        if tool_payload:

            request_kwargs["tools"] = (
                tool_payload
            )

            request_kwargs["tool_choice"] = (
                "auto"
            )

        try:

            response = (
                self._client
                .chat
                .completions
                .create(
                    **request_kwargs
                )
            )

        except Exception as exc:

            self._raise_provider_error(
                exc
            )

        try:

            if not response.choices:

                raise AIProviderError(
                    "Groq returned no choices."
                )

            choice = response.choices[0]

            message = choice.message

            content = (
                message.content
                or ""
            )

            finish_reason = getattr(
                choice,
                "finish_reason",
                None,
            )

            tool_calls = (
                self._parse_tool_calls(
                    getattr(
                        message,
                        "tool_calls",
                        None,
                    )
                )
            )

            usage = self._extract_usage(
                response
            )

            return AIResponse(
                content=content,
                model=self._model,
                finish_reason=finish_reason,
                usage=usage,
                tool_calls=tool_calls,
            )

        except AIProviderError:

            raise

        except Exception as exc:

            raise AIProviderError(
                f"Invalid response from Groq: {exc}"
            ) from exc

    # ========================================================
    # STREAMING
    # ========================================================

    def stream(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> Iterator[AIChunk]:

        self._validate_messages(
            messages
        )

        payload = [
            message.to_dict()
            for message in messages
        ]

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
            "stream": True,
        }

        tool_payload = (
            self._build_tool_payload(
                tools
            )
        )

        if tool_payload:

            request_kwargs["tools"] = (
                tool_payload
            )

            request_kwargs["tool_choice"] = (
                "auto"
            )

        # ----------------------------------------------------
        # Tool-call aggregation state.
        #
        # Streaming providers may send:
        #
        #   tool name delta
        #   argument delta
        #   argument delta
        #   ...
        #
        # We aggregate those pieces before exposing an
        # AIToolCall to the rest of Krakken.
        # ----------------------------------------------------

        tool_accumulators: dict[
            int,
            dict[str, Any],
        ] = {}

        finished = False

        try:

            response_stream = (
                self._client
                .chat
                .completions
                .create(
                    **request_kwargs
                )
            )

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

                # --------------------------------------------
                # Normal text
                # --------------------------------------------

                content = getattr(
                    delta,
                    "content",
                    None,
                )

                if content:

                    yield AIChunk(
                        content=str(content),
                        finished=False,
                    )

                # --------------------------------------------
                # Tool-call delta
                # --------------------------------------------

                raw_tool_calls = getattr(
                    delta,
                    "tool_calls",
                    None,
                )

                if raw_tool_calls:

                    self._accumulate_tool_calls(
                        tool_accumulators,
                        raw_tool_calls,
                    )

                # --------------------------------------------
                # Finish reason
                # --------------------------------------------

                finish_reason = getattr(
                    choice,
                    "finish_reason",
                    None,
                )

                if finish_reason:

                    finished = True

                    completed_tool_calls = (
                        self._finalize_tool_calls(
                            tool_accumulators
                        )
                    )

                    yield AIChunk(
                        content="",
                        finished=True,
                        finish_reason=str(
                            finish_reason
                        ),
                        tool_calls=(
                            completed_tool_calls
                        ),
                    )

                    break

            # ------------------------------------------------
            # Defensive finish.
            # ------------------------------------------------

            if not finished:

                completed_tool_calls = (
                    self._finalize_tool_calls(
                        tool_accumulators
                    )
                )

                yield AIChunk(
                    content="",
                    finished=True,
                    finish_reason="stop",
                    tool_calls=(
                        completed_tool_calls
                    ),
                )

        except AIProviderError:

            raise

        except Exception as exc:

            self._raise_provider_error(
                exc
            )

    # ========================================================
    # TOOL DEFINITIONS
    # ========================================================

    @staticmethod
    def _build_tool_payload(
        tools: Sequence[ToolDefinition] | None,
    ) -> list[dict[str, Any]]:
        """
        Convert Krakken tool definitions into Groq's tool schema.
        """

        if not tools:

            return []

        payload: list[
            dict[str, Any]
        ] = []

        for tool in tools:

            payload.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": (
                            tool.description
                        ),
                        "parameters": (
                            tool.parameters
                        ),
                    },
                }
            )

        return payload

    # ========================================================
    # TOOL CALL ACCUMULATION
    # ========================================================

    @staticmethod
    def _accumulate_tool_calls(
        accumulators: dict[
            int,
            dict[str, Any],
        ],
        raw_tool_calls: Any,
    ) -> None:
        """
        Aggregate streamed Groq tool-call deltas.
        """

        for raw_call in raw_tool_calls:

            index = getattr(
                raw_call,
                "index",
                0,
            )

            if index not in accumulators:

                accumulators[index] = {
                    "id": None,
                    "name": "",
                    "arguments": "",
                }

            state = (
                accumulators[index]
            )

            call_id = getattr(
                raw_call,
                "id",
                None,
            )

            if call_id:

                state["id"] = call_id

            function = getattr(
                raw_call,
                "function",
                None,
            )

            if function is None:

                continue

            name = getattr(
                function,
                "name",
                None,
            )

            if name:

                state["name"] += str(
                    name
                )

            arguments = getattr(
                function,
                "arguments",
                None,
            )

            if arguments:

                state["arguments"] += str(
                    arguments
                )

    # ========================================================
    # FINALIZE TOOL CALLS
    # ========================================================

    def _finalize_tool_calls(
        self,
        accumulators: dict[
            int,
            dict[str, Any],
        ],
    ) -> list[AIToolCall]:
        """
        Convert aggregated provider tool calls into normalized
        AIToolCall objects.
        """

        results: list[
            AIToolCall
        ] = []

        for index in sorted(
            accumulators
        ):

            state = (
                accumulators[index]
            )

            name = (
                state["name"]
                or ""
            ).strip()

            if not name:

                continue

            raw_arguments = (
                state["arguments"]
                or "{}"
            ).strip()

            try:

                arguments = json.loads(
                    raw_arguments
                )

            except json.JSONDecodeError as exc:

                self._log(
                    "Failed to parse tool arguments "
                    f"for '{name}': {exc}",
                    error=True,
                )

                raise AIProviderError(
                    f"Invalid JSON arguments for "
                    f"tool '{name}': {exc}"
                ) from exc

            if not isinstance(
                arguments,
                dict,
            ):

                raise AIProviderError(
                    f"Tool arguments for '{name}' "
                    "must be a JSON object."
                )

            results.append(
                AIToolCall(
                    name=name,
                    arguments=arguments,
                    call_id=state["id"],
                )
            )

        return results

    # ========================================================
    # PARSE NON-STREAMING TOOL CALLS
    # ========================================================

    @staticmethod
    def _parse_tool_calls(
        raw_tool_calls: Any,
    ) -> list[AIToolCall]:

        if not raw_tool_calls:

            return []

        results: list[
            AIToolCall
        ] = []

        for raw_call in raw_tool_calls:

            function = getattr(
                raw_call,
                "function",
                None,
            )

            if function is None:

                continue

            name = getattr(
                function,
                "name",
                "",
            )

            raw_arguments = getattr(
                function,
                "arguments",
                "{}",
            )

            try:

                arguments = json.loads(
                    raw_arguments
                    or "{}"
                )

            except json.JSONDecodeError as exc:

                raise AIProviderError(
                    f"Invalid JSON arguments for "
                    f"tool '{name}': {exc}"
                ) from exc

            if not isinstance(
                arguments,
                dict,
            ):

                raise AIProviderError(
                    f"Arguments for tool '{name}' "
                    "must be an object."
                )

            results.append(
                AIToolCall(
                    name=str(name),
                    arguments=arguments,
                    call_id=getattr(
                        raw_call,
                        "id",
                        None,
                    ),
                )
            )

        return results

    # ========================================================
    # USAGE
    # ========================================================

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> dict[str, int]:

        usage_data = getattr(
            response,
            "usage",
            None,
        )

        usage: dict[str, int] = {}

        if usage_data is None:

            return usage

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

            usage["prompt_tokens"] = int(
                prompt_tokens
            )

        if completion_tokens is not None:

            usage["completion_tokens"] = int(
                completion_tokens
            )

        if total_tokens is not None:

            usage["total_tokens"] = int(
                total_tokens
            )

        return usage

    # ========================================================
    # VALIDATION
    # ========================================================

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

            # Tool-call assistant messages may legally have
            # empty content.

            if (
                message.role != "assistant"
                and not message.content.strip()
            ):

                raise AIProviderError(
                    "Chat messages cannot contain empty content."
                )

    # ========================================================
    # ERROR
    # ========================================================

    def _raise_provider_error(
        self,
        exc: Exception,
    ) -> None:

        message = str(exc)

        if (
            "model_not_found" in message
            or "does not exist or you do not have access" in message
        ):

            message = (
                f"Configured Groq model '{self._model}' is unavailable. "
                "Update GROQ_MODEL in your .env file to a supported Groq model."
            )

        self._log(
            f"Groq request failed: {message}",
            error=True,
        )

        raise AIProviderError(
            f"Groq request failed: {message}"
        ) from exc

    # ========================================================
    # LOGGING
    # ========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:

        if self._logger is None:

            return

        try:

            if error:

                self._logger.error(
                    message
                )

            else:

                self._logger.info(
                    message
                )

        except Exception:

            pass
