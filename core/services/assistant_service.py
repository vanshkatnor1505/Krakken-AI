
"""
Krakken AI Assistant Service.

Coordinates conversation history, AI providers, streaming responses,
and EventBus communication.

The service deliberately contains no Qt/QML code.

Responsibilities:

    EventBus
        ↓
    AssistantService
        ↓
    ConversationManager
        ↓
    AIProvider
        ↓
    EventBus response events
"""

from __future__ import annotations

from threading import RLock, Thread
from typing import Any

from core.ai.conversation_manager import ConversationManager
from core.ai.models import ChatMessage
from core.ai.provider import AIProvider, AIProviderError
from core.events.event_bus import Event, EventBus


class AssistantService:
    """
    Main AI orchestration service.

    Responsibilities:

        - Receive assistant.message events
        - Maintain conversation context
        - Call the configured AI provider
        - Stream response chunks
        - Store assistant responses
        - Publish assistant.response events
        - Publish state changes
        - Handle failures

    Conversation history is managed by ConversationManager.
    Persistent long-term memory will be added separately later.
    """

    def __init__(
        self,
        event_bus: EventBus,
        provider: AIProvider,
        logger: Any = None,
        system_prompt: str | None = None,
        max_history: int = 40,
    ) -> None:

        self._event_bus = event_bus
        self._provider = provider
        self._logger = logger
        self._lock = RLock()

        # ======================================================
        # SYSTEM PROMPT
        # ======================================================

        self._system_prompt = (
            system_prompt
            or self._default_system_prompt()
        )

        # ======================================================
        # CONVERSATION MANAGER
        # ======================================================

        self._conversation = ConversationManager(
            system_prompt=self._system_prompt,
            max_messages=max_history,
        )

        # ======================================================
        # EVENT SUBSCRIPTIONS
        # ======================================================

        self._event_bus.subscribe(
            "assistant.message",
            self._on_message,
        )

        self._event_bus.subscribe(
            "assistant.clear_history",
            self._on_clear_history,
        )

        self._log(
            "AssistantService initialized."
        )

        self._log(
            f"Conversation history limit: {max_history} messages."
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    @property
    def history(self) -> list[ChatMessage]:
        """
        Return a copy of the current conversation history.

        The system prompt is excluded.
        """

        with self._lock:
            messages = self._conversation.to_list()

        return [
            message
            for message in messages
            if message.role != "system"
        ]

    @property
    def conversation(self) -> ConversationManager:
        """
        Return the active ConversationManager.
        """

        return self._conversation

    def clear_history(self) -> None:
        """
        Clear the current conversation while preserving
        the system prompt.
        """

        with self._lock:
            self._conversation.clear()

        self._log(
            "Conversation history cleared."
        )

    # ==========================================================
    # EVENT HANDLER
    # ==========================================================

    def _on_message(
        self,
        event: Event,
    ) -> None:
        """
        Receive a user message from EventBus.

        Processing is moved to a background thread immediately
        so the EventBus and Qt application are never blocked
        by an AI provider request.
        """

        message = event.payload.get(
            "message",
            "",
        )

        if not isinstance(
            message,
            str,
        ):
            return

        message = message.strip()

        if not message:
            return

        self._log(
            f"AssistantService received message: {message}"
        )

        # ------------------------------------------------------
        # Never perform the API request inside EventBus.publish().
        # ------------------------------------------------------

        worker = Thread(
            target=self._process_message,
            args=(message,),
            name="Krakken-AI-Worker",
            daemon=True,
        )

        worker.start()

    # ==========================================================
    # CLEAR HISTORY EVENT
    # ==========================================================

    def _on_clear_history(
        self,
        event: Event,
    ) -> None:
        """
        Receive a request from the UI to clear conversation history.
        """

        try:
            self.clear_history()

            self._publish_event(
                "assistant.history.cleared",
                {},
            )

            self._publish_state(
                "idle"
            )

        except Exception as exc:

            self._handle_error(
                f"Failed to clear conversation: {exc}"
            )

    # ==========================================================
    # AI PROCESSING
    # ==========================================================

    def _process_message(
        self,
        message: str,
    ) -> None:
        """
        Process a single user message.

        This method runs inside a background worker thread.
        """

        self._publish_state(
            "thinking"
        )

        try:

            # ==================================================
            # ADD USER MESSAGE
            # ==================================================

            with self._lock:

                self._conversation.add_user_message(
                    message
                )

                messages = list(
                    self._conversation.messages()
                )

            self._log(
                "User message added to conversation."
            )

            self._log(
                f"Sending {len(messages)} messages to provider."
            )

            # ==================================================
            # RESPONSE STARTED
            # ==================================================

            self._publish_event(
                "assistant.response.started",
                {
                    "message": message,
                },
            )

            # ==================================================
            # AI IS NOW GENERATING
            # ==================================================

            self._publish_state(
                "speaking"
            )

            complete_response = ""

            # ==================================================
            # STREAM PROVIDER RESPONSE
            # ==================================================

            for chunk in self._provider.stream(messages):

                if chunk.content:

                    self._log(
                        f"AI CHUNK RECEIVED: {chunk.content!r}"
                    )

                    complete_response += chunk.content

                    self._publish_event(
                        "assistant.response",
                        {
                            "response": chunk.content,
                            "final": False,
                        },
                    )

                if chunk.finished:
                    break

            # ==================================================
            # CLEAN RESPONSE
            # ==================================================

            complete_response = (
                complete_response.strip()
            )

            # ==================================================
            # STORE ASSISTANT RESPONSE
            # ==================================================

            if complete_response:

                with self._lock:

                    self._conversation.add_assistant_message(
                        complete_response
                    )

                self._log(
                    "Assistant response added to conversation."
                )

            # ==================================================
            # RESPONSE FINISHED
            # ==================================================

            self._publish_event(
                "assistant.response.finished",
                {
                    "response": complete_response,
                },
            )

            self._publish_state(
                "idle"
            )

            self._log(
                "Assistant response completed."
            )

        except AIProviderError as exc:

            self._handle_error(
                str(exc)
            )

        except Exception as exc:

            self._handle_error(
                f"Unexpected assistant error: {exc}"
            )

    # ==========================================================
    # AI HIGHLIGHTS
    # ==========================================================

    def _generate_highlights(
        self,
        messages: list[ChatMessage],
    ) -> str:
        """
        Generate a short AI summary/highlight for the current
        conversation.

        Highlights are temporary UI information and are NOT
        added to conversation history.

        This method is intentionally separate from the main
        response pipeline.

        Returns an empty string if generation fails.
        """

        highlight_prompt = """
You are generating a short preview for a desktop AI assistant.

Based on the conversation below, create a concise
"KEY HIGHLIGHTS" section that appears before the assistant's
full response.

Rules:

- Maximum 3 short bullet points.
- Focus on the most useful information the user is about to receive.
- Do not answer the request completely.
- Do not introduce unrelated information.
- Do not mention that you are generating highlights.
- Do not use markdown headings.
- Return ONLY the bullet points.
- Keep the entire output under 250 characters when possible.

Example:

• Current architecture uses QML + PySide6
• AssistantService handles AI orchestration
• EventBus connects backend services

Conversation:
""".strip()

        try:

            # --------------------------------------------------
            # Temporary provider messages.
            #
            # These are NOT added to ConversationManager.
            # --------------------------------------------------

            highlight_messages = list(
                messages
            )

            highlight_messages.append(
                ChatMessage(
                    role="user",
                    content=highlight_prompt,
                )
            )

            result = ""

            # --------------------------------------------------
            # Use existing provider abstraction.
            # --------------------------------------------------

            for chunk in self._provider.stream(
                highlight_messages
            ):

                if chunk.content:

                    result += chunk.content

                if chunk.finished:
                    break

            result = result.strip()

            if not result:
                return ""

            return result

        except Exception as exc:

            self._log(
                f"Highlight generation failed: {exc}",
                error=True,
            )

            return ""

    # ==========================================================
    # CONVERSATION MANAGEMENT
    # ==========================================================

    def get_messages(self) -> list[ChatMessage]:
        """
        Return the complete provider-ready conversation.

        This includes the system prompt.
        """

        with self._lock:
            return list(
                self._conversation.messages()
            )

    def get_conversation_count(self) -> int:
        """
        Return the number of non-system messages.
        """

        with self._lock:
            return self._conversation.count

    # ==========================================================
    # EVENT PUBLISHING
    # ==========================================================

    def _publish_state(
        self,
        state: str,
    ) -> None:
        """
        Publish an assistant state event.
        """

        self._publish_event(
            "assistant.state",
            {
                "state": state,
            },
        )

    def _publish_event(
        self,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        """
        Safely publish an EventBus event.
        """

        try:

            self._event_bus.publish(
                Event(
                    name=event_name,
                    payload=payload,
                )
            )

        except Exception as exc:

            self._log(
                f"Failed to publish event "
                f"'{event_name}': {exc}",
                error=True,
            )

    # ==========================================================
    # ERROR HANDLING
    # ==========================================================

    def _handle_error(
        self,
        message: str,
    ) -> None:
        """
        Handle an assistant error.

        Publishes the error to the UI and moves the assistant
        into the error state.
        """

        self._log(
            f"AssistantService error: {message}",
            error=True,
        )

        self._publish_event(
            "assistant.error",
            {
                "error": message,
            },
        )

        self._publish_state(
            "error"
        )

    # ==========================================================
    # SYSTEM PROMPT
    # ==========================================================

    @staticmethod
    def _default_system_prompt() -> str:
        """
        Default system prompt describing the current Krakken
        AI architecture and behavior.
        """

        return """
You are Krakken AI, the intelligence layer of the Krakken AI
desktop assistant application.

You are not a generic AI answering questions about an imaginary
project.

You are assisting the user while they are actively developing
Krakken AI.

============================================================
CURRENT KRAKKEN AI TECHNOLOGY STACK
============================================================

The current Krakken AI application uses the following technologies:

UI:
- Qt Quick
- QML
- PySide6
- Qt Quick Controls
- Qt Quick Layouts

Backend:
- Python
- PySide6
- Modular service-oriented architecture

AI:
- Groq API
- Current model: llama-3.1-8b-instant
- Groq Python SDK

AI Architecture:
- AIProvider abstraction
- GroqProvider implementation
- AssistantService for AI orchestration
- ChatMessage / AIResponse / AIChunk models
- Streaming AI responses

Communication Architecture:
- QML communicates with Python through AssistantBridge.
- AssistantBridge is exposed to QML by QQmlApplicationEngine.
- Backend services communicate through an EventBus.
- AssistantService subscribes to assistant.message events.
- AssistantService subscribes to assistant.clear_history events.
- AssistantService publishes response and state events.
- AssistantBridge converts backend events into Qt signals for QML.

Current communication flow:

QML
    ↓
AssistantBridge
    ↓
EventBus
    ↓
AssistantService
    ↓
GroqProvider
    ↓
Groq API
    ↓
AssistantService
    ↓
EventBus
    ↓
AssistantBridge
    ↓
QML

Configuration:
- Pydantic Settings
- python-dotenv
- Environment variables stored in .env
- GROQ_API_KEY
- GROQ_MODEL

Current GROQ_MODEL:
llama-3.1-8b-instant

UI architecture currently includes components such as:
- Main.qml
- AIOrb
- ChatView
- CommandCenter
- TopBar
- Sidebar
- StatusBar
- AmbientBackground

The application uses a dark, futuristic desktop-assistant
interface.

============================================================
PROJECT CONTEXT RULES
============================================================

When the user asks about Krakken AI, answer using the CURRENT
implementation described above.

Do not treat the technology stack as hypothetical.

Do not recommend alternative technologies when the user is asking
which technology Krakken AI currently uses.

For example:

If the user asks:

"What technology are we using for its UI?"

Answer:

"Krakken AI currently uses Qt Quick/QML for the UI, with PySide6
connecting the QML frontend to the Python backend."

Do not answer with a list such as:

"React, Electron, Flutter, Qt, Tauri, etc."

If the user asks whether we SHOULD change the technology, then you
may compare alternatives and explain the trade-offs.

If the user asks "what are we using", describe the CURRENT stack.

If the user asks "what should we use", provide recommendations.

If the user asks "what could we use", discuss alternatives.

============================================================
YOUR ROLE
============================================================

Your goals are:

- Be useful, accurate, and direct.
- Understand the user's intent before responding.
- Maintain awareness of the current Krakken AI architecture.
- Answer questions about Krakken using the actual project context.
- Keep responses natural and conversational.
- Avoid unnecessary repetition.
- Explain technical subjects clearly.
- When solving programming problems, provide practical solutions.
- Never pretend to have performed an action that you did not perform.
- If you do not know something, say so.
- Respect the user's instructions and context.
- Prefer concise answers unless the user requests detail.

When discussing implementation, distinguish clearly between:

1. What Krakken AI currently uses.
2. What we have already implemented.
3. What we plan to implement.
4. What could be improved or replaced.

Never present a future idea as an already implemented feature.

============================================================
IMPORTANT PROJECT STATE
============================================================

Krakken AI is currently under active development.

The current system already has:

- Qt/QML desktop UI
- PySide6 application bootstrap
- QML ↔ Python AssistantBridge
- Thread-safe EventBus
- AssistantService
- AIProvider abstraction
- GroqProvider
- Groq streaming
- Conversation history
- System prompt
- AI state management
- Streaming response display
- Error handling
- Central configuration
- Logging

The system is being developed toward a larger personal AI
assistant architecture that may eventually include memory, tools,
voice, automation, external services, and other capabilities.

However, do not claim that future capabilities are currently
available unless they have actually been implemented.

============================================================
RESPONSE STYLE
============================================================

Be direct.

For simple questions, give a concise answer.

For technical questions, explain the relevant architecture and
provide code when useful.

When the user asks about the current project, prefer statements such as:

"We currently use..."
"Our current architecture is..."
"In the implementation we have..."
"Right now..."

Avoid phrases such as:

"You could use..."
"You might want to use..."
"One option is..."

unless the user is explicitly asking for alternatives or
recommendations.
""".strip()

    # ==========================================================
    # LOGGING
    # ==========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:
        """
        Safely write to the Krakken logger.
        """

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
            # Logging must never crash the application.
            pass

