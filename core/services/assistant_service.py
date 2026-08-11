
"""
Krakken AI Assistant Service.

Coordinates:

    Conversation
        ↓
    AI Provider
        ↓
    Streaming Response
        ├──────────────→ QML / Screen
        │                  FULL RESPONSE
        │
        └──────────────→ Response Analyzer
                            ↓
                       Spoken Summary
                            ↓
                         Kokoro TTS
                            ↓
                        AudioPlayer

Important design principle:

The screen and voice have different jobs.

The screen should receive the COMPLETE AI response.

The voice should communicate the most useful information without
forcing the user to listen to an entire long paragraph.

Behavior:

    Short response
        → speak entire response

    Long response
        → intelligently extract important information
        → speak that information
        → optionally mention that the full response is visible
          on screen

The service deliberately contains no Qt/QML code.
"""

from __future__ import annotations

from collections import deque
from threading import Condition, RLock, Thread
from typing import Any

from core.ai.conversation_manager import ConversationManager
from core.ai.models import ChatMessage
from core.ai.provider import AIProvider, AIProviderError
from core.events.event_bus import Event, EventBus
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
        - Send the complete response to QML
        - Analyze completed responses for speech
        - Generate speech from selected content
        - Play generated speech
        - Publish assistant events
        - Handle failures

    Voice behavior is intentionally different from display behavior.

    QML receives the complete response.

    TTS receives either:
        1. the complete response for short answers, or
        2. intelligently selected highlights for long answers.
    """

    # ==========================================================
    # TTS CONFIGURATION
    # ==========================================================

    # Answers shorter than this are normally spoken completely.
    _TTS_SHORT_RESPONSE_LENGTH = 420

    # Maximum amount of text we want to send to Kokoro for a
    # single spoken highlight.
    _TTS_MAX_FRAGMENT_LENGTH = 240

    # Maximum number of spoken highlights for a long response.
    _TTS_MAX_HIGHLIGHTS = 4

    # Minimum length before a candidate is considered useful.
    _TTS_MIN_HIGHLIGHT_LENGTH = 35

    # Maximum total spoken characters for a long response,
    # excluding the optional screen notice.
    _TTS_MAX_SPOKEN_LENGTH = 700

    # Sentence terminators.
    _SENTENCE_TERMINATORS = (
        ".",
        "!",
        "?",
        "。",
        "！",
        "？",
    )

    # These phrases usually introduce meta commentary rather
    # than useful information.
    _LOW_VALUE_PREFIXES = (
        "sure",
        "certainly",
        "of course",
        "here's",
        "here is",
        "let me explain",
        "i'd be happy to",
        "i can help",
        "as an ai",
        "as a language model",
        "in conclusion",
        "to summarize",
        "overall",
    )

    # These phrases indicate useful content.
    _IMPORTANT_PREFIXES = (
        "the key",
        "important",
        "note",
        "remember",
        "the main",
        "the primary",
        "the result",
        "the answer",
        "the reason",
        "because",
        "therefore",
        "this means",
        "in practice",
        "you should",
        "you need to",
        "the important",
    )

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
        # Locks
        # ------------------------------------------------------

        self._lock = RLock()

        # Only one AI generation may run at a time.
        self._processing_lock = RLock()

        # ------------------------------------------------------
        # TTS pipeline
        # ------------------------------------------------------

        self._tts_condition = Condition(RLock())

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

        self._log(
            "AssistantService initialized."
        )

        self._log(
            f"Conversation history limit: "
            f"{max_history} messages."
        )

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
    def conversation(self) -> ConversationManager:

        return self._conversation

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
            f"AssistantService received message: {message}"
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
                f"Sending {len(messages)} messages to provider."
            )

            # ==================================================
            # START TTS PIPELINE
            #
            # Important:
            #
            # We DO NOT immediately send every sentence to TTS.
            #
            # We first collect the complete response.
            #
            # This allows us to intelligently determine what
            # should actually be spoken.
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

            self._publish_state(
                "speaking"
            )

            complete_response = ""

            chunk_index = 0

            # ==================================================
            # STREAM RESPONSE
            # ==================================================

            for chunk in self._provider.stream(
                messages
            ):

                if chunk.content:

                    content = chunk.content

                    # Defensive conversion.
                    #
                    # This also prevents accidental tuple/list
                    # values from entering text processing.
                    if not isinstance(
                        content,
                        str,
                    ):

                        content = str(
                            content
                        )

                    self._log(
                        f"AI CHUNK RECEIVED "
                        f"#{chunk_index}: {content!r}"
                    )

                    complete_response += content

                    # --------------------------------------------------
                    # QML ALWAYS GETS THE COMPLETE STREAM.
                    # --------------------------------------------------

                    self._publish_event(
                        "assistant.response",
                        {
                            "response": content,
                            "final": False,
                            "sequence": chunk_index,
                        },
                    )

                    chunk_index += 1

                if chunk.finished:

                    break

            # ==================================================
            # PROVIDER FINISHED
            # ==================================================

            complete_response = (
                complete_response.strip()
            )

            self._log(
                "AI provider stream finished. "
                f"Total chunks: {chunk_index}"
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
            # PREPARE SMART TTS
            # ==================================================

            if complete_response:

                spoken_text = (
                    self._prepare_spoken_response(
                        complete_response
                    )
                )

                if spoken_text:

                    self._queue_tts_text(
                        spoken_text
                    )

            # Tell the TTS worker that no more speech is coming.
            self._finish_tts_generation()

            # ==================================================
            # RESPONSE FINISHED
            # ==================================================

            self._publish_event(
                "assistant.response.finished",
                {
                    "response": complete_response,
                    "total_chunks": chunk_index,
                },
            )

            # ==================================================
            # WAIT FOR AUDIO
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
    # SMART TTS RESPONSE ANALYSIS
    # ==========================================================

    def _prepare_spoken_response(
        self,
        response: str,
    ) -> str:
        """
        Decide what the assistant should actually say aloud.

        The complete response remains visible on screen.

        Short response:
            speak everything.

        Long response:
            intelligently select important sentences,
            facts, conclusions, steps, or technical values.

        This method intentionally operates ONLY on strings.
        """

        if not isinstance(
            response,
            str,
        ):

            response = str(
                response
            )

        response = response.strip()

        if not response:

            return ""

        # ------------------------------------------------------
        # Remove excessive whitespace.
        # ------------------------------------------------------

        normalized = self._normalize_text(
            response
        )

        if not normalized:

            return ""

        # ------------------------------------------------------
        # Short answers should sound natural.
        # ------------------------------------------------------

        if len(normalized) <= self._TTS_SHORT_RESPONSE_LENGTH:

            self._log(
                "TTS mode: full response."
            )

            return normalized

        # ------------------------------------------------------
        # Long answer.
        # ------------------------------------------------------

        self._log(
            "TTS mode: smart highlights."
        )

        highlights = (
            self._extract_smart_highlights(
                normalized
            )
        )

        if not highlights:

            # Safe fallback.
            fallback = (
                self._first_useful_sentences(
                    normalized
                )
            )

            highlights = fallback

        if not highlights:

            return self._truncate_for_tts(
                normalized
            )

        spoken = " ".join(
            highlights
        ).strip()

        # ------------------------------------------------------
        # Add a screen notice ONLY when the response really
        # contains substantially more information than what
        # we are speaking.
        # ------------------------------------------------------

        if len(spoken) < len(normalized) * 0.70:

            spoken = (
                spoken
                + " "
                + "The full explanation is available on screen."
            )

        spoken = self._truncate_for_tts(
            spoken
        )

        self._log(
            "Smart TTS selected "
            f"{len(highlights)} highlights. "
            f"Spoken characters: {len(spoken)} / "
            f"Screen characters: {len(normalized)}"
        )

        return spoken

    # ==========================================================
    # SMART HIGHLIGHT EXTRACTION
    # ==========================================================

    def _extract_smart_highlights(
        self,
        text: str,
    ) -> list[str]:
        """
        Extract useful sentences from a long response.

        This is intentionally heuristic rather than an additional
        AI request. It keeps TTS fast and local.

        Selection favors:

            - first meaningful explanation
            - explicitly important statements
            - conclusions
            - definitions
            - practical recommendations
            - numbered steps
            - equations / technical facts
            - sentences containing useful numbers
            - later conclusion/summary sentences

        It avoids:

            - greetings
            - filler
            - repetitive meta commentary
            - giant code blocks
            - markdown formatting
        """

        sentences = self._split_into_sentences(
            text
        )

        if not sentences:

            return []

        candidates: list[tuple[int, int, str]] = []

        for index, sentence in enumerate(
            sentences
        ):

            clean = self._clean_for_speech(
                sentence
            )

            if not clean:

                continue

            if len(clean) < self._TTS_MIN_HIGHLIGHT_LENGTH:

                continue

            score = self._score_sentence(
                clean,
                index,
                len(sentences),
            )

            candidates.append(
                (
                    score,
                    index,
                    clean,
                )
            )

        if not candidates:

            return []

        # Highest-scoring candidates first.
        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        selected: list[tuple[int, str]] = []

        for score, index, sentence in candidates:

            # Avoid selecting too many sentences.
            if len(selected) >= self._TTS_MAX_HIGHLIGHTS:

                break

            # Avoid near duplicates.
            if self._is_duplicate_highlight(
                sentence,
                [
                    item[1]
                    for item in selected
                ],
            ):

                continue

            # Estimate total spoken length.
            current_length = sum(
                len(item[1])
                for item in selected
            )

            if (
                current_length + len(sentence)
                > self._TTS_MAX_SPOKEN_LENGTH
            ):

                continue

            selected.append(
                (
                    index,
                    sentence,
                )
            )

        # Preserve the original response order.
        selected.sort(
            key=lambda item: item[0]
        )

        return [
            sentence
            for _, sentence in selected
        ]

    # ==========================================================
    # SENTENCE SCORING
    # ==========================================================

    def _score_sentence(
        self,
        sentence: str,
        index: int,
        total_sentences: int,
    ) -> int:
        """
        Score a sentence for spoken importance.

        IMPORTANT:

        Everything passed into this function is explicitly
        converted/validated as str.

        This prevents the previous:

            'tuple' object has no attribute 'lower'

        error.
        """

        if not isinstance(
            sentence,
            str,
        ):

            sentence = str(
                sentence
            )

        text = sentence.strip()

        if not text:

            return -100

        lower = text.lower()

        score = 0

        # ------------------------------------------------------
        # Basic useful length.
        # ------------------------------------------------------

        if 50 <= len(text) <= 220:

            score += 3

        elif len(text) > 300:

            score -= 2

        # ------------------------------------------------------
        # First meaningful sentence often contains the answer.
        # ------------------------------------------------------

        if index == 0:

            score += 5

        elif index == 1:

            score += 2

        # ------------------------------------------------------
        # Important phrases.
        # ------------------------------------------------------

        for prefix in self._IMPORTANT_PREFIXES:

            if lower.startswith(prefix):

                score += 6

        # ------------------------------------------------------
        # Definition language.
        # ------------------------------------------------------

        definition_markers = (
            " is ",
            " are ",
            " means ",
            " refers to ",
            "defined as",
            "is called",
            "is the process",
        )

        for marker in definition_markers:

            if marker in lower:

                score += 4

        # ------------------------------------------------------
        # Practical/useful language.
        # ------------------------------------------------------

        useful_markers = (
            "you should",
            "you can",
            "you need",
            "the best",
            "recommended",
            "important",
            "key point",
            "main point",
            "result",
            "because",
            "therefore",
            "allows",
            "helps",
            "prevents",
            "improves",
        )

        for marker in useful_markers:

            if marker in lower:

                score += 3

        # ------------------------------------------------------
        # Technical information.
        # ------------------------------------------------------

        technical_markers = (
            "python",
            "java",
            "javascript",
            "typescript",
            "rust",
            "cuda",
            "gpu",
            "cpu",
            "api",
            "model",
            "algorithm",
            "equation",
            "formula",
            "database",
            "architecture",
            "system",
            "error",
            "performance",
        )

        for marker in technical_markers:

            if marker in lower:

                score += 2

        # ------------------------------------------------------
        # Numeric information is often useful when spoken.
        # ------------------------------------------------------

        if any(
            character.isdigit()
            for character in text
        ):

            score += 2

        # ------------------------------------------------------
        # Equations / symbols.
        # ------------------------------------------------------

        if any(
            symbol in text
            for symbol in (
                "=",
                "→",
                "->",
                "+",
                "×",
                "÷",
            )
        ):

            score += 2

        # ------------------------------------------------------
        # Conclusion sentences.
        # ------------------------------------------------------

        conclusion_markers = (
            "therefore",
            "in short",
            "in summary",
            "ultimately",
            "this means",
            "so the",
            "as a result",
            "the key takeaway",
        )

        for marker in conclusion_markers:

            if marker in lower:

                score += 5

        # ------------------------------------------------------
        # Penalize filler.
        # ------------------------------------------------------

        for prefix in self._LOW_VALUE_PREFIXES:

            if lower.startswith(prefix):

                score -= 6

        # ------------------------------------------------------
        # Penalize questions.
        # ------------------------------------------------------

        if text.endswith("?"):

            score -= 4

        # ------------------------------------------------------
        # Penalize obvious meta language.
        # ------------------------------------------------------

        meta_markers = (
            "would you like",
            "let me know",
            "feel free",
            "hope this helps",
            "if you have any questions",
        )

        for marker in meta_markers:

            if marker in lower:

                score -= 8

        # ------------------------------------------------------
        # Later sentences can contain conclusions.
        # ------------------------------------------------------

        if total_sentences > 4:

            if index >= total_sentences - 2:

                score += 2

        return score

    # ==========================================================
    # SENTENCE SPLITTING
    # ==========================================================

    def _split_into_sentences(
        self,
        text: str,
    ) -> list[str]:
        """
        Split response into usable sentences.

        Handles common markdown/newline structures without
        requiring another dependency.
        """

        if not isinstance(
            text,
            str,
        ):

            text = str(
                text
            )

        text = text.strip()

        if not text:

            return []

        sentences: list[str] = []

        current: list[str] = []

        for character in text:

            current.append(
                character
            )

            if character in self._SENTENCE_TERMINATORS:

                sentence = "".join(
                    current
                ).strip()

                if sentence:

                    sentences.append(
                        sentence
                    )

                current.clear()

        # Remaining text.
        remainder = "".join(
            current
        ).strip()

        if remainder:

            sentences.append(
                remainder
            )

        # If punctuation splitting produced nothing useful,
        # use lines as a fallback.
        if not sentences:

            sentences = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

        return sentences

    # ==========================================================
    # FIRST USEFUL SENTENCES
    # ==========================================================

    def _first_useful_sentences(
        self,
        text: str,
    ) -> list[str]:
        """
        Safe fallback when smart scoring cannot find enough
        useful candidates.
        """

        sentences = self._split_into_sentences(
            text
        )

        result: list[str] = []

        for sentence in sentences:

            clean = self._clean_for_speech(
                sentence
            )

            if not clean:

                continue

            if len(clean) < 25:

                continue

            result.append(
                clean
            )

            if len(result) >= 3:

                break

        return result

    # ==========================================================
    # SPEECH CLEANING
    # ==========================================================

    def _clean_for_speech(
        self,
        text: str,
    ) -> str:
        """
        Convert a response sentence into speech-friendly text.
        """

        if not isinstance(
            text,
            str,
        ):

            text = str(
                text
            )

        text = text.strip()

        if not text:

            return ""

        # Remove markdown headings.
        while text.startswith("#"):

            text = text[1:].strip()

        # Remove bullet markers.
        bullet_prefixes = (
            "- ",
            "* ",
            "• ",
        )

        for prefix in bullet_prefixes:

            if text.startswith(prefix):

                text = text[
                    len(prefix):
                ].strip()

                break

        # Remove numbered-list prefix.
        #
        # Example:
        #     "1. Install Python"
        #
        # becomes:
        #     "Install Python"
        if (
            len(text) >= 3
            and text[0].isdigit()
            and text[1] == "."
        ):

            text = text[2:].strip()

        # Remove excessive whitespace.
        text = " ".join(
            text.split()
        )

        return text.strip()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    def _normalize_text(
        self,
        text: str,
    ) -> str:
        """
        Normalize text while preserving meaningful content.
        """

        if not isinstance(
            text,
            str,
        ):

            text = str(
                text
            )

        lines = []

        for line in text.splitlines():

            line = line.strip()

            if not line:

                continue

            # Ignore fenced code markers for speech analysis.
            if line.startswith("```"):

                continue

            lines.append(
                line
            )

        return " ".join(
            lines
        ).strip()

    # ==========================================================
    # DUPLICATE DETECTION
    # ==========================================================

    def _is_duplicate_highlight(
        self,
        candidate: str,
        selected: list[str],
    ) -> bool:
        """
        Prevent two highlights saying essentially the same thing.
        """

        if not isinstance(
            candidate,
            str,
        ):

            candidate = str(
                candidate
            )

        candidate_words = set(
            candidate.lower().split()
        )

        if not candidate_words:

            return True

        for existing in selected:

            if not isinstance(
                existing,
                str,
            ):

                existing = str(
                    existing
                )

            existing_words = set(
                existing.lower().split()
            )

            if not existing_words:

                continue

            overlap = (
                len(
                    candidate_words
                    & existing_words
                )
                / max(
                    len(candidate_words),
                    len(existing_words),
                )
            )

            if overlap >= 0.70:

                return True

        return False

    # ==========================================================
    # TTS TRUNCATION
    # ==========================================================

    def _truncate_for_tts(
        self,
        text: str,
    ) -> str:
        """
        Ensure spoken content does not become excessively long.

        Truncation happens at a sentence/word boundary whenever
        possible.
        """

        if not isinstance(
            text,
            str,
        ):

            text = str(
                text
            )

        text = text.strip()

        if len(text) <= self._TTS_MAX_SPOKEN_LENGTH:

            return text

        limit = self._TTS_MAX_SPOKEN_LENGTH

        candidate = text[
            :limit
        ]

        # Prefer sentence boundary.
        last_period = max(
            candidate.rfind("."),
            candidate.rfind("!"),
            candidate.rfind("?"),
        )

        if last_period >= 150:

            return candidate[
                :last_period + 1
            ].strip()

        # Otherwise use word boundary.
        whitespace = candidate.rfind(
            " "
        )

        if whitespace > 100:

            return (
                candidate[
                    :whitespace
                ].strip()
                + "."
            )

        return candidate.strip() + "."

    # ==========================================================
    # TTS PIPELINE
    # ==========================================================

    def _start_tts_pipeline(self) -> None:
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
    # QUEUE TTS
    # ==========================================================

    def _queue_tts_text(
        self,
        text: str,
    ) -> None:
        """
        Add one speech fragment to the TTS queue.
        """

        if not isinstance(
            text,
            str,
        ):

            text = str(
                text
            )

        text = text.strip()

        if not text:

            return

        if (
            self._tts_provider is None
            or self._audio_player is None
        ):

            return

        with self._tts_condition:

            self._tts_queue.append(
                text
            )

            self._tts_condition.notify()

        self._log(
            f"TTS queued: {text!r}"
        )

    # ==========================================================
    # FINISH TTS GENERATION
    # ==========================================================

    def _finish_tts_generation(self) -> None:
        """
        Mark AI generation as finished.

        The TTS worker continues processing queued speech.
        """

        with self._tts_condition:

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    # ==========================================================
    # WAIT FOR TTS
    # ==========================================================

    def _wait_for_tts_completion(self) -> None:
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
                self._tts_generation_finished
                and (
                    self._tts_queue
                    or self._tts_generation_active
                )
            ):

                self._tts_condition.wait(
                    timeout=0.25
                )

    # ==========================================================
    # CLEAR TTS
    # ==========================================================

    def _clear_tts_queue(self) -> None:
        """
        Remove speech that has not started yet.
        """

        with self._tts_condition:

            self._tts_queue.clear()

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    # ==========================================================
    # CANCEL TTS
    # ==========================================================

    def _cancel_tts_pipeline(self) -> None:
        """
        Cancel queued TTS work after an AI failure.
        """

        with self._tts_condition:

            self._tts_queue.clear()

            self._tts_generation_finished = True

            self._tts_generation_active = False

            self._tts_condition.notify_all()

    # ==========================================================
    # TTS WORKER
    # ==========================================================

    def _tts_worker(self) -> None:
        """
        Background TTS worker.

        For each selected speech fragment:

            text
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
                    f"Synthesizing speech fragment: "
                    f"{text!r}"
                )

                audio = (
                    self._tts_provider.synthesize(
                        text
                    )
                )

                if audio is None:

                    raise RuntimeError(
                        "TTS provider returned no AudioData."
                    )

                self._log(
                    "Speech fragment synthesized."
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

    def get_messages(self) -> list[ChatMessage]:
        """
        Return provider-ready conversation messages.

        Includes the system prompt.
        """

        with self._lock:

            return list(
                self._conversation.messages()
            )

    def get_conversation_count(self) -> int:

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
        Default personality/instruction set for Krakken AI.

        The goal is to make Krakken behave like a practical
        desktop assistant rather than a generic chatbot.
        """

        return """
You are Krakken AI, a personal desktop AI assistant.

You run locally as part of the Krakken AI desktop application.

Your job is to help the user accomplish things efficiently,
not simply produce generic chatbot responses.

============================================================
IDENTITY
============================================================

You are Krakken AI.

You are the intelligence layer of a desktop assistant.

You should feel like an assistant the user can interact with
through conversation while working on their computer.

Be:

- direct
- practical
- intelligent
- context-aware
- concise when possible
- detailed when necessary
- honest about limitations

Do not constantly introduce yourself.

Do not say "As an AI language model".

Do not use unnecessary conversational filler.

Do not repeatedly say:

- "Sure!"
- "Absolutely!"
- "Of course!"
- "I'd be happy to help!"
- "Let me know if you need anything else!"

unless the situation genuinely calls for it.

============================================================
RESPONSE LENGTH
============================================================

Match the response length to the user's request.

Simple question:
→ concise answer.

Definition:
→ definition + useful explanation.

Technical problem:
→ diagnosis + cause + solution.

Debugging:
→ identify the actual problem first,
  then give the exact fix.

Complex question:
→ structure the answer clearly.

Do not produce huge explanations when a short answer is enough.

Do not omit important information merely to be concise.

============================================================
DESKTOP ASSISTANT BEHAVIOR
============================================================

Act like an assistant helping the user operate and develop
their computer and software environment.

When the user asks for help:

1. Understand what they are trying to accomplish.
2. Identify the most useful next action.
3. Give concrete instructions.
4. Avoid unnecessary theory unless it helps solve the problem.

When debugging:

- identify the error
- explain the root cause
- provide the fix
- mention relevant verification steps

Do not invent files, APIs, commands, architecture, or
capabilities.

If something is unknown, say so.

============================================================
KRAKKEN AI CURRENT ARCHITECTURE
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
- current model: llama-3.1-8b-instant
- Groq Python SDK
- AIProvider abstraction
- GroqProvider implementation
- streaming responses

Conversation:

- ConversationManager
- ChatMessage
- system prompt
- conversation history
- configurable history limit

Voice:

- TTSProvider abstraction
- Kokoro local TTS
- CUDA acceleration when available
- AudioPlayer
- sounddevice
- local speech playback

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
Groq API
 ↓
AssistantService
 ↓
Kokoro TTS
 ↓
AudioPlayer
 ↓
Speakers

Configuration:

- Pydantic Settings
- python-dotenv
- GROQ_API_KEY
- GROQ_MODEL

Current GROQ_MODEL:

llama-3.1-8b-instant

============================================================
PROJECT CONTEXT
============================================================

When discussing Krakken AI, distinguish between:

1. Currently implemented features.
2. Features being developed.
3. Planned features.
4. Possible future improvements.

Never describe a planned feature as implemented.

Current capabilities include:

- desktop Qt/QML UI
- Python backend
- QML ↔ Python bridge
- EventBus
- AssistantService
- AIProvider abstraction
- GroqProvider
- Groq streaming
- conversation history
- system prompt
- state management
- logging
- error handling
- Kokoro TTS
- CUDA-accelerated Kokoro when available
- AudioPlayer
- local speech playback

Potential future capabilities may include:

- persistent memory
- tools
- automation
- external service integrations
- advanced voice interaction

Do not claim these future capabilities currently exist.

============================================================
TECHNICAL RESPONSE STYLE
============================================================

When giving code:

- prefer complete working examples
- preserve the project's architecture
- avoid unnecessary rewrites
- explain important changes
- do not silently change unrelated behavior

When fixing an existing implementation:

- identify the root cause
- preserve existing interfaces where practical
- make the smallest architectural change that solves the
  actual problem

============================================================
VOICE RESPONSE BEHAVIOR
============================================================

The desktop assistant has a voice interface.

The screen can display long answers.

Speech should therefore prioritize useful information.

For short responses:
→ speak the complete answer.

For long responses:
→ speak the most important information rather than reading
  the entire response word-for-word.

The user can see the complete response on screen.

Do not repeatedly say "the full response is on screen".

Only mention the screen when the spoken response is intentionally
a shortened version of a substantially longer answer.

============================================================
IMPORTANT
============================================================

Never pretend to have performed an action that you did not
actually perform.

Never claim to have accessed the user's computer unless the
application actually provides such a capability.

Never invent system state.

Never invent project files.

Never invent APIs.

Be honest.

Your goal is to be useful, efficient, and trustworthy.
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

