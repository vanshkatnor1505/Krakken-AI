"""
Conversation manager for Krakken AI.

Maintains the current conversation history and prepares
messages for the AI provider.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.ai.models import ChatMessage


class ConversationManager:
    """
    Manages the active AI conversation.

    Conversation history is kept separate from persistent memory.
    """

    def __init__(
        self,
        system_prompt: str,
        max_messages: int = 40,
    ) -> None:

        self.max_messages = max(
            2,
            max_messages,
        )

        self.system_message = ChatMessage(
            role="system",
            content=system_prompt,
        )

        self._messages: list[ChatMessage] = []

        self.reset()

    # ==========================================================
    # RESET
    # ==========================================================

    def reset(self) -> None:
        """
        Start a fresh conversation.
        """

        self._messages.clear()

        self._messages.append(
            self.system_message
        )

    # ==========================================================
    # ADD MESSAGE
    # ==========================================================

    def add_user_message(
        self,
        content: str,
    ) -> None:

        content = content.strip()

        if not content:
            return

        self._messages.append(
            ChatMessage(
                role="user",
                content=content,
            )
        )

        self._trim()

    def add_assistant_message(
        self,
        content: str,
    ) -> None:

        content = content.strip()

        if not content:
            return

        self._messages.append(
            ChatMessage(
                role="assistant",
                content=content,
            )
        )

        self._trim()

    # ==========================================================
    # HISTORY
    # ==========================================================

    def messages(self) -> Sequence[ChatMessage]:
        """
        Return the current conversation.

        A tuple is returned so callers cannot accidentally
        modify the internal history.
        """

        return tuple(
            self._messages
        )

    # ==========================================================
    # LAST MESSAGE
    # ==========================================================

    @property
    def last_message(self) -> ChatMessage | None:

        if not self._messages:
            return None

        return self._messages[-1]

    # ==========================================================
    # COUNT
    # ==========================================================

    @property
    def count(self) -> int:

        # Exclude the system prompt.
        return max(
            0,
            len(self._messages) - 1,
        )

    # ==========================================================
    # TRIM HISTORY
    # ==========================================================

    def _trim(self) -> None:
        """
        Keep the system prompt plus the most recent messages.
        """

        maximum_history = self.max_messages - 1

        if len(self._messages) <= self.max_messages:
            return

        recent = self._messages[
            -maximum_history:
        ]

        self._messages = [
            self.system_message,
            *recent,
        ]

    # ==========================================================
    # EXPORT
    # ==========================================================

    def to_list(self) -> list[ChatMessage]:
        """
        Return a copy of the current conversation.
        """

        return list(
            self._messages
        )

    # ==========================================================
    # CLEAR
    # ==========================================================

    def clear(self) -> None:
        """
        Clear the conversation while preserving the system prompt.
        """

        self.reset()