"""
Data models used by the Krakken AI engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Role = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]


@dataclass(slots=True)
class ChatMessage:
    """
    A single conversation message.
    """

    role: Role
    content: str
    name: str | None = None

    def to_dict(self) -> dict[str, str]:
        """
        Convert the message into the format expected by
        chat-completion providers.
        """

        data: dict[str, str] = {
            "role": self.role,
            "content": self.content,
        }

        if self.name:
            data["name"] = self.name

        return data


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


@dataclass(slots=True)
class AIChunk:
    """
    A streaming response chunk.
    """

    content: str
    finished: bool = False
    finish_reason: str | None = None