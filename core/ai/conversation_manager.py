
"""
Krakken AI - Conversation Manager.

Responsible for managing the active conversation history.

Responsibilities:

    - Store conversation messages
    - Preserve the system prompt
    - Add user messages
    - Add assistant messages
    - Enforce maximum history size
    - Provide provider-ready messages
    - Clear conversation history

This class contains no Qt/QML code.
It is independent of the AI provider and EventBus.
"""

from __future__ import annotations

from threading import RLock

from core.ai.models import ChatMessage


class ConversationManager:
    """
    Manages the conversation history used by Krakken AI.

    The system prompt is always preserved at the beginning
    of the conversation.

    Example:

        ConversationManager
            ↓
        [system]
        [user]
        [assistant]
        [user]
        [assistant]
    """

    def __init__(
        self,
        system_prompt: str,
        max_messages: int = 40,
    ) -> None:

        if not isinstance(
            system_prompt,
            str,
        ):
            raise TypeError(
                "system_prompt must be a string."
            )

        if max_messages <= 0:
            raise ValueError(
                "max_messages must be greater than zero."
            )

        self._lock = RLock()

        self._system_prompt = system_prompt.strip()

        self._max_messages = max_messages

        self._messages: list[ChatMessage] = []

        # ------------------------------------------------------
        # Always initialize with the system prompt.
        # ------------------------------------------------------

        self._messages.append(
            ChatMessage(
                role="system",
                content=self._system_prompt,
            )
        )

    # ==========================================================
    # PROPERTIES
    # ==========================================================

    @property
    def system_prompt(self) -> str:
        """
        Return the current system prompt.
        """

        return self._system_prompt

    @property
    def max_messages(self) -> int:
        """
        Return the maximum number of non-system messages
        retained in conversation history.
        """

        return self._max_messages

    @property
    def count(self) -> int:
        """
        Return the number of non-system messages.

        The system prompt is intentionally excluded.
        """

        with self._lock:

            return max(
                0,
                len(self._messages) - 1,
            )

    # ==========================================================
    # MESSAGE ACCESS
    # ==========================================================

    def messages(self) -> list[ChatMessage]:
        """
        Return a copy of the complete conversation.

        Includes the system prompt.
        """

        with self._lock:

            return list(
                self._messages
            )

    def to_list(self) -> list[ChatMessage]:
        """
        Return a copy of the complete conversation.

        This is provided as a convenient compatibility API
        for AssistantService.history.
        """

        with self._lock:

            return list(
                self._messages
            )

    # ==========================================================
    # ADD USER MESSAGE
    # ==========================================================

    def add_user_message(
        self,
        content: str,
    ) -> None:
        """
        Add a user message to the conversation.
        """

        self._add_message(
            ChatMessage(
                role="user",
                content=self._validate_content(
                    content
                ),
            )
        )

    # ==========================================================
    # ADD ASSISTANT MESSAGE
    # ==========================================================

    def add_assistant_message(
        self,
        content: str,
    ) -> None:
        """
        Add an assistant message to the conversation.
        """

        self._add_message(
            ChatMessage(
                role="assistant",
                content=self._validate_content(
                    content
                ),
            )
        )

    # ==========================================================
    # GENERIC MESSAGE
    # ==========================================================

    def add_message(
        self,
        message: ChatMessage,
    ) -> None:
        """
        Add an arbitrary ChatMessage.

        Useful for future tool/function messages.
        """

        if not isinstance(
            message,
            ChatMessage,
        ):
            raise TypeError(
                "message must be a ChatMessage instance."
            )

        if message.role == "system":

            raise ValueError(
                "System messages cannot be added "
                "through add_message()."
            )

        self._add_message(
            message
        )

    # ==========================================================
    # INTERNAL MESSAGE HANDLING
    # ==========================================================

    def _add_message(
        self,
        message: ChatMessage,
    ) -> None:
        """
        Add a message and enforce the history limit.

        The system prompt is never removed.
        """

        with self._lock:

            self._messages.append(
                message
            )

            self._trim_history()

    # ==========================================================
    # HISTORY LIMIT
    # ==========================================================

    def _trim_history(self) -> None:
        """
        Keep only the newest non-system messages.

        Example:

            max_messages = 4

            system
            user
            assistant
            user
            assistant

        Older messages are removed first.
        """

        # System message + max non-system messages.
        maximum_total_messages = (
            1 +
            self._max_messages
        )

        while (
            len(self._messages)
            > maximum_total_messages
        ):

            # Never remove index 0 because it is
            # the system prompt.
            self._messages.pop(1)

    # ==========================================================
    # CLEAR
    # ==========================================================

    def clear(self) -> None:
        """
        Clear all conversation messages while preserving
        the system prompt.
        """

        with self._lock:

            self._messages.clear()

            self._messages.append(
                ChatMessage(
                    role="system",
                    content=self._system_prompt,
                )
            )

    # ==========================================================
    # UPDATE SYSTEM PROMPT
    # ==========================================================

    def set_system_prompt(
        self,
        system_prompt: str,
    ) -> None:
        """
        Replace the current system prompt.

        Existing conversation messages are preserved.
        """

        system_prompt = self._validate_content(
            system_prompt
        )

        with self._lock:

            self._system_prompt = system_prompt

            self._messages[0] = ChatMessage(
                role="system",
                content=system_prompt,
            )

    # ==========================================================
    # LAST MESSAGE
    # ==========================================================

    def last_message(
        self,
    ) -> ChatMessage | None:
        """
        Return the most recent message.

        Returns None when the conversation contains
        only the system prompt.
        """

        with self._lock:

            if len(self._messages) <= 1:
                return None

            return self._messages[-1]

    # ==========================================================
    # LAST USER MESSAGE
    # ==========================================================

    def last_user_message(
        self,
    ) -> ChatMessage | None:
        """
        Return the most recent user message.
        """

        with self._lock:

            for message in reversed(
                self._messages
            ):

                if message.role == "user":

                    return message

        return None

    # ==========================================================
    # LAST ASSISTANT MESSAGE
    # ==========================================================

    def last_assistant_message(
        self,
    ) -> ChatMessage | None:
        """
        Return the most recent assistant message.
        """

        with self._lock:

            for message in reversed(
                self._messages
            ):

                if message.role == "assistant":

                    return message

        return None

    # ==========================================================
    # REMOVE LAST MESSAGE
    # ==========================================================

    def remove_last_message(
        self,
    ) -> ChatMessage | None:
        """
        Remove and return the newest non-system message.

        The system prompt can never be removed.
        """

        with self._lock:

            if len(self._messages) <= 1:

                return None

            return self._messages.pop()

    # ==========================================================
    # VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_content(
        content: str,
    ) -> str:
        """
        Validate and normalize message content.
        """

        if not isinstance(
            content,
            str,
        ):
            raise TypeError(
                "Message content must be a string."
            )

        content = content.strip()

        if not content:

            raise ValueError(
                "Message content cannot be empty."
            )

        return content

