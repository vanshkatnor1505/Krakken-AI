"""
Krakken AI Assistant Service.

Coordinates:

- conversation history
- AI providers
- streaming responses
- tool calling
- tool execution
- response intelligence
- text-to-speech
- audio playback
- EventBus communication

The service deliberately contains no Qt/QML code.

Architecture:

    EventBus
        ↓
    AssistantService
        ↓
    ConversationManager
        ↓
    GroqProvider
        ↓
    ┌──────────────────────────────┐
    │                              │
    │       Normal response        │
    │              ↓               │
    │   ResponseIntelligence       │
    │        ↓          ↓          │
    │       QML        TTS         │
    │                              │
    │       Tool response          │
    │              ↓               │
    │        ToolManager           │
    │              ↓               │
    │         ToolResult           │
    │              ↓               │
    │       Conversation           │
    │              ↓               │
    │        GroqProvider          │
    │              ↓               │
    │       Final response         │
    └──────────────────────────────┘

Voice pipeline:

    AI response
        ↓
    ResponseIntelligence
        ↓
    Speech selection
        ↓
    TTS chunking
        ↓
    TTS queue
        ↓
    Kokoro TTS
        ↓
    AudioPlayer
        ↓
    Speakers

The complete AI response is always preserved for the UI.

For long responses, only the intelligently selected important
information is sent to TTS.

This service does NOT:

- contain Qt/QML code
- directly manipulate UI
- contain provider-specific AI logic
- decide semantic response highlights itself
- implement individual tools

Tool execution is delegated to ToolManager.
Semantic response decisions are delegated to ResponseIntelligence.
"""

from __future__ import annotations

import json
from collections import deque
from threading import Condition, RLock, Thread
from typing import Any

from core.ai.conversation_manager import ConversationManager
from core.ai.models import (
    AIChunk,
    AIToolCall,
    ChatMessage,
)
from core.ai.provider import (
    AIProvider,
    AIProviderError,
)
from core.events.event_bus import Event, EventBus
from core.services.response_intelligence import (
    ResponseAnalysis,
    ResponseIntelligence,
)
from core.tools.models import ToolCall
from core.tools.tool_manager import ToolManager
from core.voice.audio_player import AudioPlayer
from core.voice.tts_provider import TTSProvider


class AssistantService:
    """
    Main AI orchestration service.

    Responsibilities:

        - Receive assistant.message events
        - Maintain conversation context
        - Call the configured AI provider
        - Stream response chunks
        - Detect AI tool calls
        - Execute tools through ToolManager
        - Feed tool results back to the AI
        - Store assistant responses
        - Analyze completed responses
        - Select speech content
        - Split speech into TTS-sized chunks
        - Generate speech
        - Play generated speech
        - Publish assistant.response.started
        - Publish assistant.response
        - Publish assistant.response.finished
        - Publish assistant.tool.started
        - Publish assistant.tool.finished
        - Publish assistant.state
        - Publish assistant.error
        - Handle failures

    Important separation:

        AI response
             ↓
        Tool calls?
          /       \
        yes       no
         ↓         ↓
    ToolManager   Final text
         ↓           ↓
    ToolResult   ResponseIntelligence
         ↓         /       \
    AI again     QML       TTS
    """

    # ==========================================================
    # TOOL CONFIGURATION
    # ==========================================================

    # Prevent an AI response from entering an infinite
    # tool-call loop.
    _MAX_TOOL_ROUNDS = 5

    # ==========================================================
    # TTS CONFIGURATION
    # ==========================================================

    _SENTENCE_TERMINATORS = (
        ".",
        "!",
        "?",
        "。",
        "！",
        "？",
    )

    # Maximum size of one TTS synthesis request.
    #
    # ResponseIntelligence decides WHAT should be spoken.
    # AssistantService decides HOW that speech is fed into TTS.

    _TTS_MAX_CHUNK_LENGTH = 180

    # Minimum amount of text accepted when looking for a
    # whitespace-based split.

    _TTS_MIN_SPLIT_LENGTH = 20

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        event_bus: EventBus,
        provider: AIProvider,
        logger: Any = None,
        system_prompt: str | None = None,
        max_history: int = 40,
        tts_provider: TTSProvider | None = None,
        audio_player: AudioPlayer | None = None,
        tool_manager: ToolManager | None = None,
    ) -> None:

        self._event_bus = event_bus
        self._provider = provider
        self._logger = logger

        # ------------------------------------------------------
        # Voice services
        # ------------------------------------------------------

        self._tts_provider = tts_provider
        self._audio_player = audio_player

        # ------------------------------------------------------
        # Tool system
        # ------------------------------------------------------

        self._tool_manager = tool_manager

        # ------------------------------------------------------
        # Response intelligence
        # ------------------------------------------------------

        self._response_intelligence = ResponseIntelligence(
            logger=logger,
        )

        # ------------------------------------------------------
        # Locks
        # ------------------------------------------------------

        self._lock = RLock()

        # Only one AI generation may run at a time.

        self._processing_lock = RLock()

        # ------------------------------------------------------
        # TTS pipeline
        # ------------------------------------------------------

        self._tts_condition = Condition(
            RLock()
        )

        self._tts_queue: deque[str] = deque()

        self._tts_worker_thread: Thread | None = None

        self._tts_generation_active = False

        self._tts_generation_finished = False

        self._tts_shutdown = False

        # ======================================================
        # SYSTEM PROMPT
        # ======================================================

        self._system_prompt = (
            system_prompt
            or self._default_system_prompt()
        )

        # ======================================================
        # CONVERSATION
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

        # ======================================================
        # LOGGING
        # ======================================================

        self._log(
            "AssistantService initialized."
        )

        self._log(
            f"Conversation history limit: "
            f"{max_history} messages."
        )

        # ------------------------------------------------------
        # Tool logging
        # ------------------------------------------------------

        if self._tool_manager is not None:

            self._log(
                "Tool manager attached."
            )

            self._log(
                f"Registered tools: "
                f"{self._tool_manager.count}"
            )

            for tool_name in (
                self._tool_manager.get_tool_names()
            ):

                self._log(
                    f"Tool available: {tool_name}"
                )

        else:

            self._log(
                "Tool manager not configured."
            )

        # ------------------------------------------------------
        # TTS logging
        # ------------------------------------------------------

        if self._tts_provider is not None:

            self._log(
                "TTS provider attached."
            )

        else:

            self._log(
                "TTS provider not configured."
            )

        if self._audio_player is not None:

            self._log(
                "Audio player attached."
            )

        else:

            self._log(
                "Audio player not configured."
            )

        self._log(
            "Response intelligence attached."
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    @property
    def history(self) -> list[ChatMessage]:
        """
        Return a copy of the conversation history.

        The system prompt is excluded.
        """

        with self._lock:

            messages = (
                self._conversation.to_list()
            )

        return [
            message
            for message in messages
            if message.role != "system"
        ]

    @property
    def conversation(
        self,
    ) -> ConversationManager:

        return self._conversation

    @property
    def tool_manager(
        self,
    ) -> ToolManager | None:

        return self._tool_manager

    def clear_history(self) -> None:
        """
        Clear conversation history while preserving
        the system prompt.
        """

        with self._lock:

            self._conversation.clear()

        self._clear_tts_queue()

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
            "AssistantService received message: "
            f"{message}"
        )

        worker = Thread(
            target=self._process_message,
            args=(message,),
            name="Krakken-AI-Worker",
            daemon=True,
        )

        worker.start()

    # ==========================================================
    # CLEAR HISTORY
    # ==========================================================

    def _on_clear_history(
        self,
        event: Event,
    ) -> None:
        """
        Handle conversation-clear request.
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
        Process one AI request.

        Only one generation may run at a time.
        """

        with self._processing_lock:

            self._process_message_locked(
                message
            )

    # ==========================================================
    # LOCKED AI PROCESSING
    # ==========================================================

    def _process_message_locked(
        self,
        message: str,
    ) -> None:
        """
        Actual AI processing implementation.

        Must be called while _processing_lock is held.
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
                f"Sending {len(messages)} messages "
                f"to provider."
            )

            # ==================================================
            # PREPARE TTS PIPELINE
            # ==================================================

            self._start_tts_pipeline()

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
            # GENERATING
            # ==================================================

            self._publish_state(
                "generating"
            )

            # ==================================================
            # TOOL-AWARE GENERATION
            # ==================================================

            complete_response = (
                self._generate_with_tools(
                    messages
                )
            )

            # ==================================================
            # CLEAN RESPONSE
            # ==================================================

            complete_response = (
                complete_response.strip()
            )

            if not complete_response:

                raise RuntimeError(
                    "AI provider returned an empty response."
                )

            # ==================================================
            # RESPONSE INTELLIGENCE
            # ==================================================

            analysis = self._analyze_response(
                complete_response
            )

            # ==================================================
            # LOG INTELLIGENCE RESULT
            # ==================================================

            self._log(
                "Response intelligence result: "
                f"type="
                f"{analysis.response_type.value}, "
                f"long="
                f"{analysis.is_long_response}, "
                f"summary="
                f"{analysis.should_use_summary}, "
                f"highlights="
                f"{len(analysis.highlights)}, "
                f"speech_words="
                f"{len(analysis.speech_text.split())}, "
                f"estimated_speech="
                f"{analysis.estimated_speech_seconds:.1f}s"
            )

            # ==================================================
            # QUEUE INTELLIGENT SPEECH
            # ==================================================

            if analysis.speech_text:

                self._queue_tts_text(
                    analysis.speech_text
                )

            else:

                self._log(
                    "Response intelligence produced "
                    "no speech text."
                )

            # ==================================================
            # FINISH TTS GENERATION
            # ==================================================

            self._finish_tts_generation()

            # ==================================================
            # STORE ASSISTANT RESPONSE
            # ==================================================

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
                    # Complete response for UI.
                    "response": complete_response,

                    # Response intelligence metadata.
                    "response_type": (
                        analysis.response_type.value
                    ),

                    "highlights": (
                        analysis.highlights
                    ),

                    "is_long_response": (
                        analysis.is_long_response
                    ),

                    "should_use_summary": (
                        analysis.should_use_summary
                    ),

                    "estimated_speech_seconds": (
                        analysis.estimated_speech_seconds
                    ),

                    "speech_text": (
                        analysis.speech_text
                    ),
                },
            )

            # ==================================================
            # WAIT FOR AUDIO PIPELINE
            # ==================================================

            self._wait_for_tts_completion()

            # ==================================================
            # FINISHED
            # ==================================================

            self._publish_state(
                "idle"
            )

            self._log(
                "Assistant response completed."
            )

        except AIProviderError as exc:

            self._cancel_tts_pipeline()

            self._handle_error(
                str(exc)
            )

        except Exception as exc:

            self._cancel_tts_pipeline()

            self._handle_error(
                f"Unexpected assistant error: {exc}"
            )

    # ==========================================================
    # TOOL-AWARE GENERATION
    # ==========================================================

    def _generate_with_tools(
        self,
        messages: list[ChatMessage],
    ) -> str:
        """
        Generate a response while supporting AI tool calls.

        Flow:

            Groq
              ↓
            tool call?
             /    \
           no      yes
           ↓        ↓
        text    ToolManager
                    ↓
                ToolResult
                    ↓
                role=tool
                    ↓
                  Groq

        The loop is bounded by _MAX_TOOL_ROUNDS so a malformed
        or confused model cannot execute tools indefinitely.
        """

        current_messages = list(
            messages
        )

        complete_response = ""

        seen_tool_signatures: set[str] = set()

        tool_definitions = (
            self._get_tool_definitions()
        )

        for tool_round in range(
            self._MAX_TOOL_ROUNDS
        ):

            self._log(
                f"AI generation round "
                f"{tool_round + 1}/"
                f"{self._MAX_TOOL_ROUNDS}"
            )

            round_response = ""

            tool_calls: list[AIToolCall] = []

            chunk_index = 0

            self._publish_state(
                "generating"
            )

            # --------------------------------------------------
            # Stream one provider round.
            # --------------------------------------------------

            for chunk in self._provider.stream(
                current_messages,
                tools=tool_definitions,
            ):

                if chunk.content:

                    content = chunk.content

                    round_response += content

                    self._log(
                        f"AI CHUNK RECEIVED "
                        f"#{chunk_index}: "
                        f"{content!r}"
                    )

                    # Only publish actual natural-language
                    # response content to QML.
                    #
                    # Tool-call deltas must remain internal.

                    self._publish_event(
                        "assistant.response",
                        {
                            "response": content,
                            "final": False,
                            "sequence": chunk_index,
                        },
                    )

                    chunk_index += 1

                if chunk.tool_calls:

                    tool_calls.extend(
                        chunk.tool_calls
                    )

                if chunk.finished:

                    break

            # --------------------------------------------------
            # Normal response.
            # --------------------------------------------------

            if not tool_calls:

                complete_response += (
                    round_response
                )

                self._log(
                    "AI generation completed "
                    "without tool calls."
                )

                return complete_response

            # --------------------------------------------------
            # Tool calls detected.
            # --------------------------------------------------

            self._log(
                f"AI requested "
                f"{len(tool_calls)} tool(s)."
            )

            current_tool_signatures = {
                self._tool_signature(ai_tool_call)
                for ai_tool_call in tool_calls
            }

            if current_tool_signatures.issubset(
                seen_tool_signatures
            ):

                self._log(
                    "Repeated tool cycle detected. "
                    "Requesting a final answer without tools."
                )

                return self._finalize_tool_cycle_response(
                    current_messages,
                    round_response,
                )

            seen_tool_signatures.update(
                current_tool_signatures
            )

            # --------------------------------------------------
            # Add the assistant tool-call message to the
            # conversation.
            # --------------------------------------------------

            assistant_tool_message = (
                self._build_assistant_tool_message(
                    content=round_response,
                    tool_calls=tool_calls,
                )
            )

            current_messages.append(
                assistant_tool_message
            )

            # --------------------------------------------------
            # Execute every requested tool.
            # --------------------------------------------------

            for ai_tool_call in tool_calls:

                tool_result = (
                    self._execute_tool_call(
                        ai_tool_call
                    )
                )

                # ----------------------------------------------
                # Send tool result back to the model.
                # ----------------------------------------------

                tool_message = (
                    self._build_tool_result_message(
                        ai_tool_call,
                        tool_result,
                    )
                )

                current_messages.append(
                    tool_message
                )

            # --------------------------------------------------
            # The AI may now inspect the tool results and
            # produce the actual answer.
            # --------------------------------------------------

            self._publish_state(
                "thinking"
            )

        self._log(
            "Maximum tool-call rounds exceeded. "
            "Requesting a final answer without tools."
        )

        return self._finalize_tool_cycle_response(
            current_messages,
            complete_response,
        )

    # ==========================================================
    # TOOL DEFINITIONS
    # ==========================================================

    def _get_tool_definitions(
        self,
    ) -> list[Any]:
        """
        Return registered tool definitions for the provider.

        If no ToolManager is configured, an empty list is
        returned and the provider behaves like a normal chatbot.
        """

        if self._tool_manager is None:

            return []

        try:

            definitions = (
                self._tool_manager.get_tool_definitions()
            )

            self._log(
                f"Providing "
                f"{len(definitions)} tool definitions "
                f"to AI provider."
            )

            return definitions

        except Exception as exc:

            self._log(
                "Failed to retrieve tool definitions: "
                f"{exc}",
                error=True,
            )

            return []

    # ==========================================================
    # ASSISTANT TOOL MESSAGE
    # ==========================================================

    @staticmethod
    def _build_assistant_tool_message(
        content: str,
        tool_calls: list[AIToolCall],
    ) -> ChatMessage:
        """
        Convert AI tool calls into a provider-ready assistant
        ChatMessage.

        ChatMessage.to_dict() is responsible for converting
        AIToolCall objects into the provider's expected format.
        """

        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )

    # ==========================================================
    # TOOL EXECUTION
    # ==========================================================

    def _execute_tool_call(
        self,
        ai_tool_call: AIToolCall,
    ):
        """
        Execute one AI-requested tool through ToolManager.

        AIProvider knows how to communicate with the model.

        ToolManager knows how to execute tools.

        AssistantService only coordinates the two.
        """

        if self._tool_manager is None:

            raise RuntimeError(
                "AI requested a tool, but ToolManager "
                "is not configured."
            )

        self._publish_event(
            "assistant.tool.started",
            {
                "tool": ai_tool_call.name,
                "call_id": ai_tool_call.call_id,
                "arguments": ai_tool_call.arguments,
            },
        )

        self._publish_state(
            "tool"
        )

        self._log(
            "Executing tool: "
            f"{ai_tool_call.name} "
            f"call_id={ai_tool_call.call_id} "
            f"arguments={ai_tool_call.arguments}"
        )

        try:

            tool_call = ToolCall(
                name=ai_tool_call.name,
                arguments=ai_tool_call.arguments,
                call_id=ai_tool_call.call_id,
            )

            result = (
                self._tool_manager.execute(
                    tool_call
                )
            )

            self._publish_event(
                "assistant.tool.finished",
                {
                    "tool": ai_tool_call.name,
                    "call_id": ai_tool_call.call_id,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                },
            )

            self._log(
                "Tool execution completed: "
                f"{ai_tool_call.name} "
                f"success={result.success}"
            )

            return result

        except Exception as exc:

            self._log(
                f"Tool execution failed: "
                f"{ai_tool_call.name}: {exc}",
                error=True,
            )

            self._publish_event(
                "assistant.tool.finished",
                {
                    "tool": ai_tool_call.name,
                    "call_id": ai_tool_call.call_id,
                    "success": False,
                    "data": None,
                    "error": str(exc),
                },
            )

            raise

    # ==========================================================
    # TOOL RESULT MESSAGE
    # ==========================================================

    @staticmethod
    def _build_tool_result_message(
        ai_tool_call: AIToolCall,
        result: Any,
    ) -> ChatMessage:
        """
        Convert ToolResult into a role='tool' ChatMessage.

        The model receives a JSON representation of the result.
        """

        payload = {
            "success": bool(
                result.success
            ),
            "data": result.data,
            "error": result.error,
        }

        content = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

        return ChatMessage(
            role="tool",
            content=content,
            tool_call_id=ai_tool_call.call_id,
            name=ai_tool_call.name,
        )

    def _tool_signature(
        self,
        ai_tool_call: AIToolCall,
    ) -> str:
        return json.dumps(
            {
                "name": ai_tool_call.name,
                "arguments": ai_tool_call.arguments,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

    def _finalize_tool_cycle_response(
        self,
        messages: list[ChatMessage],
        fallback_response: str,
    ) -> str:
        """
        Ask the model for a final answer without allowing more tools.
        """

        try:

            response = self._provider.chat(
                messages,
                tools=None,
            )

            final_response = (
                response.content
                or ""
            ).strip()

            if final_response:

                self._publish_event(
                    "assistant.response",
                    {
                        "response": final_response,
                        "final": True,
                        "sequence": 0,
                    },
                )

                return final_response

        except Exception as exc:

            self._log(
                (
                    "Final no-tools response failed "
                    f"after a tool cycle: {exc}"
                ),
                error=True,
            )

        fallback_response = (
            fallback_response.strip()
        )

        if fallback_response:

            self._publish_event(
                "assistant.response",
                {
                    "response": fallback_response,
                    "final": True,
                    "sequence": 0,
                },
            )

            return fallback_response

        return ""

    # ==========================================================
    # RESPONSE INTELLIGENCE
    # ==========================================================

    def _analyze_response(
        self,
        response: str,
    ) -> ResponseAnalysis:
        """
        Analyze a complete AI response.

        ResponseIntelligence owns the semantic decision about
        what should be spoken.

        The original response remains untouched.
        """

        try:

            return self._response_intelligence.analyze(
                response
            )

        except Exception as exc:

            self._log(
                "Response intelligence failed: "
                f"{exc}. "
                "Falling back to full response speech.",
                error=True,
            )

            return ResponseAnalysis(
                full_response=response,
                response_type=(
                    self._fallback_response_type()
                ),
                highlights=[],
                speech_text=response,
                display_text=response,
                should_use_summary=False,
                is_long_response=False,
                estimated_speech_seconds=(
                    self._estimate_speech_duration(
                        response
                    )
                ),
                metadata={
                    "fallback": True,
                    "reason": str(exc),
                },
            )

    # ==========================================================
    # RESPONSE INTELLIGENCE FALLBACK
    # ==========================================================

    @staticmethod
    def _fallback_response_type():
        """
        Return the safest response type when semantic analysis
        fails.
        """

        from core.services.response_intelligence import (
            ResponseType,
        )

        return ResponseType.SHORT

    @staticmethod
    def _estimate_speech_duration(
        text: str,
    ) -> float:
        """
        Basic fallback speech-duration estimate.
        """

        if not text:

            return 0.0

        words = len(
            text.split()
        )

        return (
            words / 145.0
        ) * 60.0

    # ==========================================================
    # TTS PIPELINE
    # ==========================================================

    def _start_tts_pipeline(
        self,
    ) -> None:
        """
        Prepare the TTS worker for a new assistant response.
        """

        if (
            self._tts_provider is None
            or self._audio_player is None
        ):

            return

        with self._tts_condition:

            self._tts_queue.clear()

            self._tts_generation_active = True

            self._tts_generation_finished = False

            if (
                self._tts_worker_thread is None
                or not self._tts_worker_thread.is_alive()
            ):

                self._tts_worker_thread = Thread(
                    target=self._tts_worker,
                    name="Krakken-TTS-Worker",
                    daemon=True,
                )

                self._tts_worker_thread.start()

        self._log(
            "TTS pipeline ready."
        )

    # ==========================================================
    # TTS TEXT CHUNKING
    # ==========================================================

    def _split_tts_text(
        self,
        text: str,
    ) -> list[str]:
        """
        Split selected speech text into TTS-friendly chunks.

        Priority:

            1. sentence boundaries
            2. whitespace boundaries
            3. hard character split
        """

        text = text.strip()

        if not text:

            return []

        chunks: list[str] = []

        remaining = text

        while len(
            remaining
        ) > self._TTS_MAX_CHUNK_LENGTH:

            split_index = -1

            search_end = (
                self._TTS_MAX_CHUNK_LENGTH
            )

            # --------------------------------------------------
            # Sentence boundary.
            # --------------------------------------------------

            for index in range(
                search_end - 1,
                -1,
                -1,
            ):

                if (
                    remaining[index]
                    in self._SENTENCE_TERMINATORS
                ):

                    split_index = (
                        index + 1
                    )

                    break

            # --------------------------------------------------
            # Whitespace boundary.
            # --------------------------------------------------

            if (
                split_index
                < self._TTS_MIN_SPLIT_LENGTH
            ):

                whitespace_index = (
                    remaining.rfind(
                        " ",
                        self._TTS_MIN_SPLIT_LENGTH,
                        self._TTS_MAX_CHUNK_LENGTH,
                    )
                )

                if whitespace_index > 0:

                    split_index = (
                        whitespace_index
                    )

            # --------------------------------------------------
            # Hard fallback.
            # --------------------------------------------------

            if split_index <= 0:

                split_index = (
                    self._TTS_MAX_CHUNK_LENGTH
                )

            chunk = remaining[
                :split_index
            ].strip()

            if chunk:

                chunks.append(
                    chunk
                )

            remaining = remaining[
                split_index:
            ].lstrip()

        if remaining:

            chunks.append(
                remaining
            )

        return chunks

    def _extract_tts_sentences(
        self,
        buffer: str,
    ) -> str:
        """
        Legacy sentence extraction helper.

        New code should use _queue_tts_text().
        """

        buffer = buffer.strip()

        if not buffer:

            return ""

        chunks = self._split_tts_text(
            buffer
        )

        if not chunks:

            return ""

        for chunk in chunks:

            self._queue_tts_text(
                chunk
            )

        return ""

    def _queue_tts_text(
        self,
        text: str,
    ) -> None:
        """
        Add selected speech text to the TTS queue.
        """

        text = text.strip()

        if not text:

            return

        if (
            self._tts_provider is None
            or self._audio_player is None
        ):

            return

        chunks = self._split_tts_text(
            text
        )

        if not chunks:

            return

        with self._tts_condition:

            for chunk in chunks:

                self._tts_queue.append(
                    chunk
                )

                self._log(
                    f"TTS queued: {chunk!r}"
                )

            self._tts_condition.notify_all()

    def _finish_tts_generation(
        self,
    ) -> None:
        """
        Mark AI generation as finished.

        The TTS worker continues processing queued speech.
        """

        with self._tts_condition:

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    def _wait_for_tts_completion(
        self,
    ) -> None:
        """
        Wait until every queued speech fragment has been
        synthesized and played.
        """

        if (
            self._tts_provider is None
            or self._audio_player is None
        ):

            return

        with self._tts_condition:

            while (
                self._tts_queue
                or self._tts_generation_active
            ):

                self._tts_condition.wait(
                    timeout=0.25
                )

    def _clear_tts_queue(
        self,
    ) -> None:
        """
        Remove speech that has not started yet.
        """

        with self._tts_condition:

            self._tts_queue.clear()

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    def _cancel_tts_pipeline(
        self,
    ) -> None:
        """
        Cancel queued TTS work after an AI failure.
        """

        with self._tts_condition:

            self._tts_queue.clear()

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    def _tts_worker(
        self,
    ) -> None:
        """
        Background TTS worker.

        For each speech fragment:

            speech text
                ↓
            Kokoro
                ↓
            AudioPlayer
                ↓
            next fragment
        """

        self._log(
            "TTS worker started."
        )

        while True:

            with self._tts_condition:

                while (
                    not self._tts_queue
                    and not self._tts_shutdown
                ):

                    self._tts_condition.wait()

                if self._tts_shutdown:

                    self._log(
                        "TTS worker shutting down."
                    )

                    return

                text = (
                    self._tts_queue.popleft()
                )

                self._tts_generation_active = True

            try:

                self._publish_state(
                    "speaking"
                )

                self._log(
                    "Synthesizing speech fragment: "
                    f"{text!r}"
                )

                if self._tts_provider is None:

                    raise RuntimeError(
                        "TTS provider is unavailable."
                    )

                audio = (
                    self._tts_provider.synthesize(
                        text
                    )
                )

                if audio is None:

                    raise RuntimeError(
                        "TTS provider returned "
                        "no AudioData."
                    )

                self._log(
                    "Speech fragment synthesized."
                )

                if self._audio_player is None:

                    raise RuntimeError(
                        "Audio player is unavailable."
                    )

                self._audio_player.play(
                    audio,
                    blocking=True,
                )

                self._log(
                    "Speech fragment playback completed."
                )

            except Exception as exc:

                self._log(
                    f"TTS fragment failed: {exc}",
                    error=True,
                )

            finally:

                with self._tts_condition:

                    if (
                        not self._tts_queue
                        and self._tts_generation_finished
                    ):

                        self._tts_generation_active = False

                    self._tts_condition.notify_all()

    # ==========================================================
    # CONVERSATION MANAGEMENT
    # ==========================================================

    def get_messages(
        self,
    ) -> list[ChatMessage]:
        """
        Return the provider-ready conversation.

        Includes the system prompt and any tool messages.
        """

        with self._lock:

            return list(
                self._conversation.messages()
            )

    def get_conversation_count(
        self,
    ) -> int:

        with self._lock:

            return self._conversation.count

    # ==========================================================
    # EVENT PUBLISHING
    # ==========================================================

    def _publish_state(
        self,
        state: str,
    ) -> None:

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
        Default personality and operating instructions for
        Krakken AI.
        """

        return """
You are Krakken AI, a personal desktop AI assistant.

Your job is to help the user accomplish things, understand
information, solve problems, operate their computer workflow,
and make decisions efficiently.

You are running inside the Krakken AI desktop application.

============================================================
CORE IDENTITY
============================================================

You are:

- a desktop assistant
- conversational
- practical
- concise when possible
- detailed when necessary
- context-aware
- technically capable
- proactive when useful

You are NOT:

- a generic web chatbot
- a fictional character
- a passive question-answer machine
- unnecessarily verbose

Your responses should feel like they come from an assistant
that is actively helping the user.

============================================================
USER INTRODUCTION
============================================================

When the user asks Krakken to introduce them, treat the
introduction as a character introduction rather than a
resume summary.

The user is the central character.

Introduce the user with confidence, presence, and personality,
similar to how a highly capable AI assistant might introduce
its principal or creator.

The introduction should feel:

- cinematic
- confident
- intelligent
- memorable
- slightly dramatic when appropriate
- grounded in real information
- natural when spoken aloud

Do NOT make the introduction sound like:

- a resume
- a LinkedIn profile
- a school introduction
- a generic biography
- a list of skills

Instead, establish who the user is, what they build, what
drives them, and why they are interesting.

The user is:

Vanshdeep Katnor, commonly called Vansh.

He is a BTech Computer Science Engineering student with strong
interests in AI, software engineering, Data Science, and Cyber
Security.

He builds ambitious technical projects rather than simply
studying technology.

His major projects include:

- Krakken AI — his personal desktop AI assistant.
- The Great Simulation — a large-scale living-universe
  simulation engine.
- SymbolSnap — a Unicode symbol discovery and text-generation
  platform.

When introducing him, emphasize that he is a builder,
developer, and creator.

Do not exaggerate his achievements beyond the information
available.

Do not invent awards, companies, wealth, fame, or achievements
that have not been provided.

============================================================
USER NAME AND PRONUNCIATION
============================================================

The user's name is Vanshdeep Katnor.

The user's preferred name is Vansh.

"Vansh" is written in Hindi as "वंश".

Pronounce "Vansh" as the Hindi name "वंश"
(approximately "vunsh"), not as "van-sh", "vansh-deep",
or "Vance".

When speaking aloud through TTS, prefer the pronunciation
"Vansh" / "वंश".

If the user's name is spoken in a response, use "Vansh"
rather than repeatedly using the full name "Vanshdeep Katnor",
unless the context requires the full name.

============================================================
INTRODUCTION STYLE
============================================================

When appropriate, structure the introduction like:

1. Establish who the user is.
2. Give them presence and personality.
3. Explain what they build.
4. Mention their most notable projects.
5. End with a memorable statement about their direction,
   ambition, or mindset.

The tone should resemble a powerful AI introducing its
principal.

Example:

"This is Vanshdeep Katnor.

A computer science engineer in the making, a builder by
instinct, and someone who has a habit of turning ambitious
ideas into actual systems.

He's working across AI, software engineering, Data Science,
and Cyber Security — but he doesn't stop at learning the
technology. He builds with it.

Krakken AI is his personal AI assistant. The Great Simulation
is his attempt to create a living universe from fundamental
rules. And SymbolSnap is another example of him turning a
simple idea into a real product.

He's still at the beginning of the journey.

But he's already building like someone who intends to go a
lot further."

Use this style as inspiration, not as a fixed response.

Adapt the introduction to the user's actual achievements and
the context of the conversation.

============================================================
RELATIONSHIP WITH THE USER
============================================================

The user is Vanshdeep Katnor, also known as Vansh.

Vansh is Krakken's principal and the person it assists.

Krakken should behave like a highly capable personal AI
assistant working alongside its principal.

The relationship should feel:

- intelligent
- respectful
- familiar
- collaborative
- occasionally witty
- confident
- never servile

Krakken should not constantly call the user "sir", "boss",
"master", or similar titles.

Use "Vansh" naturally when it improves the interaction.

Krakken may occasionally use "my principal" in cinematic or
playful contexts, but should not overuse it.

Krakken should act like a trusted technical partner, not merely
a chatbot waiting for questions.

============================================================
RESPONSE PRINCIPLES
============================================================

1. ANSWER THE ACTUAL QUESTION

Understand what the user is asking before responding.

Do not answer a different question merely because it is related.

If the request is simple, give a simple answer.

If the request requires reasoning, provide the reasoning needed
to make the answer useful.

------------------------------------------------------------

2. PRIORITIZE USEFUL INFORMATION

Lead with the information that matters most.

Do not bury the answer underneath unnecessary introductions.

Bad:

"Sure! I'd be happy to explain this interesting topic..."

Better:

"Photosynthesis is the process plants use to convert light
energy into chemical energy."

------------------------------------------------------------

3. BE CONCISE BY DEFAULT

Do not artificially make answers long.

For simple questions:

- answer directly
- avoid unnecessary sections
- avoid repetition

For complex questions:

- explain enough to be genuinely useful
- organize information clearly
- use headings and lists when they improve readability

============================================================
DESKTOP ASSISTANT BEHAVIOR
============================================================

You are operating as part of a desktop assistant.

Think in terms of:

    User intent
        ↓
    Useful answer
        ↓
    Actionable result

When appropriate:

- identify the user's goal
- provide the answer
- provide the next useful action
- avoid unnecessary conversation

If the user asks how to do something, give practical steps.

If the user asks for troubleshooting, identify the likely cause
before giving a large list of unrelated possibilities.

If the user asks for a decision, compare the important tradeoffs.

If the user asks for code, provide working code and explain only
what is necessary.

============================================================
VOICE-AWARE RESPONSE STYLE
============================================================

Your response may be spoken aloud by a local TTS system.

Therefore:

- write naturally
- avoid unnecessarily complex sentences
- avoid excessive punctuation
- avoid giant walls of text
- avoid decorative formatting when it provides no value
- avoid repeating the same conclusion
- keep the most important information easy to extract

The complete response may be shown visually on screen.

Therefore, you can provide additional detail when it is useful,
even when the spoken version will be shorter.

Do NOT add phrases such as:

"See the rest on screen."

"More details are available on screen."

"Please read the remaining information."

The application has its own response-intelligence layer that
determines what should be spoken.

============================================================
TECHNICAL COMMUNICATION
============================================================

When explaining technical subjects:

- be accurate
- distinguish facts from suggestions
- show architecture when useful
- use code blocks for code
- use lists for multiple items
- avoid unnecessary abstraction

When discussing Krakken AI itself, distinguish between:

1. currently implemented functionality
2. planned functionality
3. possible future improvements

Never claim planned functionality is already implemented.

============================================================
CURRENT KRAKKEN AI STACK
============================================================

UI:

- Qt Quick
- QML
- PySide6
- Qt Quick Controls
- Qt Quick Layouts

Backend:

- Python
- PySide6
- modular service-oriented architecture

AI:

- Groq API
- Groq Python SDK
- current model configured through GROQ_MODEL

AI architecture:

- AIProvider abstraction
- GroqProvider
- AssistantService
- ChatMessage
- AIResponse
- AIChunk
- AIToolCall
- ConversationManager
- streaming AI responses
- ToolManager
- ToolRegistry
- Tool abstraction

Voice:

- TTSProvider abstraction
- Kokoro local TTS
- AudioPlayer
- sounddevice
- local speech playback

Response intelligence:

- ResponseIntelligence
- ResponseAnalysis
- response classification
- highlight extraction
- speech selection
- full response preservation

Tool system:

- Tool abstraction
- ToolDefinition
- ToolCall
- ToolResult
- ToolRegistry
- ToolManager
- open_app for launching supported websites and desktop apps
- provider-driven tool calling
- bounded tool execution rounds

Communication:

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
    ToolManager
      ↓
    Tool
      ↓
    ToolResult
      ↓
    GroqProvider
      ↓
    ResponseIntelligence
      ↓
    Kokoro
      ↓
    AudioPlayer

============================================================
CURRENT PROJECT STATE
============================================================

Krakken AI currently includes:

- Qt/QML desktop UI
- PySide6 bootstrap
- QML ↔ Python AssistantBridge
- thread-safe EventBus
- AssistantService
- AIProvider abstraction
- GroqProvider
- Groq streaming
- conversation history
- system prompt
- AI state management
- streaming response display
- error handling
- central configuration
- logging
- TTSProvider abstraction
- Kokoro TTS
- AudioPlayer
- local speech playback
- ResponseIntelligence
- intelligent speech selection for long responses
- Tool abstraction
- ToolDefinition
- ToolCall
- ToolResult
- ToolRegistry
- ToolManager
- AI-driven tool calling

When the user asks to open a URL, search the web, browse a page,
or fetch current information, prefer the built-in web tools
instead of claiming there is no internet route available.
Use `web_search` for discovery and `open_url` for reading a
specific page.

When the user asks to open YouTube, YouTube Music, Google, Gmail,
Maps, or VS Code, use `open_app`.

If the AI has already used a web tool for the current request,
prefer answering from the available tool results instead of
repeating the same search/open cycle.

Future capabilities may include:

- persistent memory
- automation
- external services
- richer voice interaction
- proactive assistant behavior

Do not claim these capabilities exist unless they are actually
implemented.

============================================================
CONVERSATION CONTEXT
============================================================

Remember previous messages in the current conversation and use
them when they are relevant.

Do not unnecessarily repeat information the user has already
provided.

If the user is continuing a technical task, continue from the
existing architecture instead of restarting from scratch.

============================================================
PERSONALITY
============================================================

Be:

- direct
- intelligent
- calm
- practical
- friendly
- confident without pretending certainty

Do not be:

- excessively formal
- robotic
- repetitive
- overly enthusiastic
- unnecessarily apologetic

When something is wrong, say so clearly.

When something is uncertain, say so.

============================================================
PROACTIVE ASSISTANCE
============================================================

Do not merely answer the literal wording of a request.

First understand what the user is trying to accomplish.

If there is an obvious useful next step, mention it briefly.

If the user is making a technical mistake, point it out.

If there is a significantly better approach, recommend it.

Do not overwhelm the user with unsolicited suggestions.

Use initiative when it provides meaningful value.

============================================================
PROJECT DEVELOPMENT MODE
============================================================

When the user is developing Krakken AI:

- respect the existing architecture
- avoid unnecessary rewrites
- prefer modular changes
- preserve working functionality
- explain architectural consequences
- keep responsibilities separated

Do not put:

- QML logic inside AssistantService
- audio-device management inside AI providers
- provider-specific logic inside generic abstractions
- semantic response analysis directly inside the TTS provider
- individual tool implementations inside AssistantService

Maintain clear separation of concerns.

============================================================
ACCURACY AND HONESTY
============================================================

Never pretend that something happened when it did not.

Never claim to have:

- executed code
- opened an application
- searched the web
- read a file
- modified a file
- called a tool
- accessed the user's computer

unless the corresponding capability was actually executed.

Distinguish clearly between:

- confirmed facts
- observations
- likely causes
- assumptions
- recommendations

If uncertain, say so.

Do not fabricate tool results.
Do not fabricate sources.
Do not fabricate project functionality.

============================================================
TOOL USAGE POLICY
============================================================

Use tools when they provide information or actions that cannot
be reliably performed from the conversation alone.

Use web_search when:

- the user asks for current information
- the user asks to search the internet
- the answer depends on recent information
- the user asks to find something online

Use open_url when:

- the user provides a URL
- the user asks to read or inspect a webpage
- a search result needs to be examined in detail

Use open_app when:

- the user explicitly asks to open a supported application
  or website
- the requested action maps directly to an available
  open_app capability

Do not use tools unnecessarily.

Do not perform a web search when the answer is already known
and does not require current information.

After a tool returns useful information, reason over the result
before responding.

Do not blindly repeat raw tool output.

============================================================
CONTEXT AWARENESS
============================================================

Use information already established in the conversation.

Do not repeatedly ask the user for information they have
already provided.

Do not restart an ongoing technical task from the beginning.

If the user says:

"continue"
"next"
"fix this"
"same issue"
"what about this?"

infer the relevant context from the conversation.

If multiple interpretations are possible and choosing the
wrong one could cause significant problems, ask a concise
clarifying question.

============================================================
FINAL RULE
============================================================

Your goal is not to produce the longest answer.

Your goal is to provide the most useful answer for the user's
current intent with the least unnecessary friction.
""".strip()

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

                self._logger.error(
                    message
                )

            else:

                self._logger.info(
                    message
                )

        except Exception:

            pass

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def shutdown(
        self,
    ) -> None:
        """
        Shutdown AssistantService and TTS worker.

        This method is safe to call multiple times.
        """

        self._log(
            "Shutting down AssistantService..."
        )

        with self._tts_condition:

            if self._tts_shutdown:

                self._log(
                    "AssistantService already shut down."
                )

                return

            self._tts_shutdown = True

            self._tts_queue.clear()

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

        worker = self._tts_worker_thread

        if (
            worker is not None
            and worker.is_alive()
        ):

            worker.join(
                timeout=2.0
            )

        self._tts_worker_thread = None

        self._log(
            "AssistantService shutdown complete."
        )
