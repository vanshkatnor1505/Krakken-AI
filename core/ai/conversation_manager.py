"""
Conversation management for Krakken AI.

Maintains provider-ready conversation history while preserving
the system prompt.

Supports:

    system messages
    user messages
    assistant messages
    assistant tool calls
    tool results
"""

from __future__ import annotations

from threading import RLock

from core.ai.models import (
    AIToolCall,
    ChatMessage,
)


class ConversationManager:
    """
    Thread-safe conversation history manager.
    """

    def __init__(
        self,
        system_prompt: str,
        max_messages: int = 40,
    ) -> None:

        if max_messages < 1:

            raise ValueError(
                "max_messages must be at least 1."
            )

        self._lock = RLock()

        self._system_prompt = (
            system_prompt.strip()
        )

        self._max_messages = (
            max_messages
        )

        self._messages: list[
            ChatMessage
        ] = []

        self._messages.append(
            ChatMessage(
                role="system",
                content=self._system_prompt,
            )
        )

    # ========================================================
    # ADD MESSAGES
    # ========================================================

    def add_user_message(
        self,
        content: str,
    ) -> None:

        self._add(
            ChatMessage(
                role="user",
                content=content,
            )
        )

    def add_assistant_message(
        self,
        content: str,
    ) -> None:

        self._add(
            ChatMessage(
                role="assistant",
                content=content,
            )
        )

    def add_assistant_tool_calls(
        self,
        content: str,
        tool_calls: list[AIToolCall],
    ) -> None:
        """
        Store an assistant message containing tool calls.
        """

        self._add(
            ChatMessage(
                role="assistant",
                content=content,
                tool_calls=tool_calls,
            )
        )

    def add_tool_message(
        self,
        content: str,
        tool_call_id: str,
        name: str | None = None,
    ) -> None:
        """
        Store the result returned by a tool.
        """

        self._add(
            ChatMessage(
                role="tool",
                content=content,
                tool_call_id=tool_call_id,
                name=name,
            )
        )

    # ========================================================
    # INTERNAL ADD
    # ========================================================

    def _add(
        self,
        message: ChatMessage,
    ) -> None:

        with self._lock:

            self._messages.append(
                message
            )

            self._trim()

    # ========================================================
    # HISTORY
    # ========================================================

    def messages(
        self,
    ) -> list[ChatMessage]:

        with self._lock:

            return list(
                self._messages
            )

    def to_list(
        self,
    ) -> list[ChatMessage]:

        return self.messages()

    # ========================================================
    # COUNT
    # ========================================================

    @property
    def count(self) -> int:

        with self._lock:

            return len(
                [
                    message
                    for message in self._messages
                    if message.role != "system"
                ]
            )

    # ========================================================
    # CLEAR
    # ========================================================

    def clear(self) -> None:

        with self._lock:

            self._messages.clear()

            self._messages.append(
                ChatMessage(
                    role="system",
                    content=self._system_prompt,
                )
            )

    # ========================================================
    # TRIMMING
    # ========================================================

    def _trim(self) -> None:
        """
        Keep the system prompt and the most recent messages.

        Tool-call groups are treated conservatively. We avoid
        trimming in the middle of a very recent interaction
        whenever possible.
        """

        system_message = self._messages[0]

        conversation = (
            self._messages[1:]
        )

        if len(conversation) <= self._max_messages:

            return

        conversation = conversation[
            -self._max_messages:
        ]

        self._messages = [
            system_message,
            *conversation,
        ]