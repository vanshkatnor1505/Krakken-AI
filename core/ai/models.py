"""
Data models used by the Krakken AI engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ============================================================
# MESSAGE ROLES
# ============================================================

Role = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]


# ============================================================
# TOOL CALL
# ============================================================


@dataclass(slots=True)
class AIToolCall:
    """
    Tool call requested by the AI provider.

    This represents the normalized tool-call structure used
    internally by Krakken.

    Provider-specific formats must be converted into this model
    inside the provider implementation.
    """

    name: str

    arguments: dict[str, Any] = field(
        default_factory=dict
    )

    call_id: str | None = None


# ============================================================
# CHAT MESSAGE
# ============================================================


@dataclass(slots=True)
class ChatMessage:
    """
    A single conversation message.

    Supports normal messages as well as assistant/tool messages
    required for tool calling.
    """

    role: Role

    content: str

    name: str | None = None

    tool_call_id: str | None = None

    tool_calls: list[AIToolCall] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the message into the provider-compatible format.

        Tool-call information is preserved when present.
        """

        data: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }

        if self.name:
            data["name"] = self.name

        if self.tool_call_id:
            data["tool_call_id"] = (
                self.tool_call_id
            )

        if self.tool_calls:

            data["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": _serialize_arguments(
                            call.arguments
                        ),
                    },
                }
                for call in self.tool_calls
            ]

        return data


# ============================================================
# AI RESPONSE
# ============================================================


@dataclass(slots=True)
class AIResponse:
    """
    Complete response returned by an AI provider.
    """

    content: str

    model: str

    finish_reason: str | None = None

    usage: dict[str, int] = field(
        default_factory=dict
    )

    tool_calls: list[AIToolCall] = field(
        default_factory=list
    )


# ============================================================
# AI STREAM CHUNK
# ============================================================


@dataclass(slots=True)
class AIChunk:
    """
    A normalized streaming response chunk.

    Content contains normal assistant text.

    tool_calls contains completed/normalized tool calls
    emitted by the provider.

    Providers may internally receive many partial tool-call
    deltas but should aggregate them before yielding the final
    AIToolCall objects here.
    """

    content: str = ""

    finished: bool = False

    finish_reason: str | None = None

    tool_calls: list[AIToolCall] = field(
        default_factory=list
    )


# ============================================================
# INTERNAL UTILITIES
# ============================================================


def _serialize_arguments(
    arguments: dict[str, Any],
) -> str:
    """
    Serialize tool arguments into JSON.

    Groq expects the function arguments in the assistant
    tool-call message as a JSON string.
    """

    import json

    return json.dumps(
        arguments,
        ensure_ascii=False,
    )