"""
Krakken AI - Response Intelligence.

Determines how an AI response should be presented and spoken.

Responsibilities:

    Full AI response
          ↓
    ResponseIntelligence
          ↓
    ┌─────────────────────────────┐
    │ response classification     │
    │ importance detection        │
    │ highlight extraction        │
    │ speech selection            │
    │ display preparation         │
    └─────────────────────────────┘
          ↓
    UI + TTS

This module does NOT:

- call the AI provider
- perform TTS
- play audio
- interact with QML
- manage conversation history
- modify the original AI response

The original response always remains available for display.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

# ============================================================
# RESPONSE TYPE
# ============================================================


class ResponseType(str, Enum):
    """
    Broad classification of an assistant response.
    """

    SHORT = "short"

    EXPLANATION = "explanation"

    LIST = "list"

    STEPS = "steps"

    CODE = "code"

    DEFINITION = "definition"

    COMPARISON = "comparison"

    ERROR = "error"

    MIXED = "mixed"


# ============================================================
# INTELLIGENCE RESULT
# ============================================================


@dataclass(slots=True)
class ResponseAnalysis:
    """
    Result produced by ResponseIntelligence.
    """

    full_response: str

    response_type: ResponseType

    highlights: list[str]

    speech_text: str

    display_text: str

    should_use_summary: bool

    is_long_response: bool

    estimated_speech_seconds: float

    metadata: dict[str, Any]


# ============================================================
# RESPONSE INTELLIGENCE
# ============================================================


class ResponseIntelligence:
    """
    Determines the optimal presentation strategy for an
    assistant response.

    The important distinction is:

        DISPLAY ≠ SPEECH

    The UI should normally receive the complete response.

    TTS should receive only the intelligently selected
    important information when the response is large.
    """

    # --------------------------------------------------------
    # Length configuration
    # --------------------------------------------------------

    DEFAULT_SHORT_CHARACTER_LIMIT = 700

    DEFAULT_SHORT_WORD_LIMIT = 120

    DEFAULT_SPEECH_WORD_LIMIT = 75

    DEFAULT_MAX_HIGHLIGHTS = 5

    # Approximate conversational speech speed.

    WORDS_PER_MINUTE = 145

    # --------------------------------------------------------
    # Sentence splitting
    # --------------------------------------------------------

    SENTENCE_PATTERN = re.compile(
        r"""
        (?<=[.!?。！？])
        \s+
        """,
        re.VERBOSE,
    )

    # --------------------------------------------------------
    # Markdown cleanup
    # --------------------------------------------------------

    CODE_BLOCK_PATTERN = re.compile(
        r"```.*?```",
        re.DOTALL,
    )

    INLINE_CODE_PATTERN = re.compile(
        r"`([^`]+)`"
    )

    MARKDOWN_LINK_PATTERN = re.compile(
        r"\[([^\]]+)\]\([^)]+\)"
    )

    MARKDOWN_HEADING_PATTERN = re.compile(
        r"^\s*#{1,6}\s*",
        re.MULTILINE,
    )

    BULLET_PATTERN = re.compile(
        r"^\s*(?:[-*•]|\d+[.)])\s+",
        re.MULTILINE,
    )

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        logger: Any = None,
        short_character_limit: int = DEFAULT_SHORT_CHARACTER_LIMIT,
        short_word_limit: int = DEFAULT_SHORT_WORD_LIMIT,
        speech_word_limit: int = DEFAULT_SPEECH_WORD_LIMIT,
        max_highlights: int = DEFAULT_MAX_HIGHLIGHTS,
    ) -> None:

        self._logger = logger

        self._short_character_limit = (
            short_character_limit
        )

        self._short_word_limit = (
            short_word_limit
        )

        self._speech_word_limit = (
            speech_word_limit
        )

        self._max_highlights = (
            max_highlights
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def analyze(
        self,
        response: str,
    ) -> ResponseAnalysis:
        """
        Analyze an assistant response.

        The returned object contains both the complete response
        and the speech-oriented representation.
        """

        if not isinstance(response, str):

            raise TypeError(
                "Response must be a string."
            )

        response = response.strip()

        if not response:

            return ResponseAnalysis(
                full_response="",
                response_type=ResponseType.SHORT,
                highlights=[],
                speech_text="",
                display_text="",
                should_use_summary=False,
                is_long_response=False,
                estimated_speech_seconds=0.0,
                metadata={},
            )

        self._log(
            "Analyzing assistant response."
        )

        clean_text = self._clean_for_analysis(
            response
        )

        words = self._word_count(
            clean_text
        )

        is_long = (
            len(clean_text)
            > self._short_character_limit
            or words
            > self._short_word_limit
        )

        response_type = (
            self._classify_response(
                response
            )
        )

        sentences = self._split_sentences(
            clean_text
        )

        highlights = self._extract_highlights(
            sentences=sentences,
            response_type=response_type,
        )

        if is_long:

            speech_text = (
                self._build_speech_summary(
                    highlights=highlights,
                    response_type=response_type,
                )
            )

            speech_text = (
                self._limit_speech_length(
                    speech_text
                )
            )

        else:

            speech_text = (
                self._clean_for_speech(
                    response
                )
            )

        should_use_summary = (
            is_long
            and speech_text != clean_text
        )

        estimated_seconds = (
            self._estimate_speech_duration(
                speech_text
            )
        )

        metadata = {
            "word_count": words,
            "character_count": len(response),
            "sentence_count": len(sentences),
            "highlight_count": len(highlights),
            "response_type": response_type.value,
        }

        self._log(
            "Response analysis complete. "
            f"Type={response_type.value}, "
            f"Words={words}, "
            f"Long={is_long}, "
            f"Summary={should_use_summary}"
        )

        return ResponseAnalysis(
            full_response=response,
            response_type=response_type,
            highlights=highlights,
            speech_text=speech_text,
            display_text=response,
            should_use_summary=should_use_summary,
            is_long_response=is_long,
            estimated_speech_seconds=estimated_seconds,
            metadata=metadata,
        )

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    def _classify_response(
        self,
        text: str,
    ) -> ResponseType:
        """
        Classify the general structure of the response.
        """

        stripped = text.strip()

        # ----------------------------------------------------
        # Code
        # ----------------------------------------------------

        if "```" in stripped:

            return ResponseType.CODE

        # ----------------------------------------------------
        # Error
        # ----------------------------------------------------

        error_patterns = (
            "error:",
            "exception:",
            "traceback",
            "failed:",
            "failure:",
        )

        lowered = stripped.lower()

        if any(
            pattern in lowered
            for pattern in error_patterns
        ):

            return ResponseType.ERROR

        # ----------------------------------------------------
        # Definition
        # ----------------------------------------------------

        definition_patterns = (
            " is ",
            " are ",
            " refers to ",
            " means ",
            " is defined as ",
        )

        first_part = (
            lowered[:300]
        )

        if any(
            pattern in first_part
            for pattern in definition_patterns
        ):

            return ResponseType.DEFINITION

        # ----------------------------------------------------
        # Steps
        # ----------------------------------------------------

        step_matches = re.findall(
            r"(?im)^\s*(?:\d+[.)]|step\s+\d+)",
            stripped,
        )

        if len(step_matches) >= 2:

            return ResponseType.STEPS

        # ----------------------------------------------------
        # Lists
        # ----------------------------------------------------

        bullet_matches = re.findall(
            r"(?m)^\s*(?:[-*•]|\d+[.)])\s+",
            stripped,
        )

        if len(bullet_matches) >= 3:

            return ResponseType.LIST

        # ----------------------------------------------------
        # Comparison
        # ----------------------------------------------------

        comparison_words = (
            " versus ",
            " vs ",
            " compared to ",
            " difference between ",
            " whereas ",
            " on the other hand ",
        )

        if any(
            word in lowered
            for word in comparison_words
        ):

            return ResponseType.COMPARISON

        # ----------------------------------------------------
        # Short response
        # ----------------------------------------------------

        if (
            self._word_count(stripped)
            <= self._short_word_limit
        ):

            return ResponseType.SHORT

        # ----------------------------------------------------
        # Default
        # ----------------------------------------------------

        return ResponseType.EXPLANATION

    # ========================================================
    # SENTENCE PROCESSING
    # ========================================================

    def _split_sentences(
        self,
        text: str,
    ) -> list[str]:
        """
        Split text into reasonably meaningful sentences.
        """

        if not text:

            return []

        sentences = (
            self.SENTENCE_PATTERN.split(
                text
            )
        )

        result = []

        for sentence in sentences:

            sentence = (
                sentence.strip()
            )

            if not sentence:

                continue

            result.append(
                sentence
            )

        return result

    # ========================================================
    # HIGHLIGHT EXTRACTION
    # ========================================================

    def _extract_highlights(
        self,
        sentences: list[str],
        response_type: ResponseType,
    ) -> list[str]:
        """
        Select the most informative sentences.

        This deliberately does NOT simply take the first
        N sentences.

        The selection considers:

        - sentence position
        - sentence length
        - keywords
        - structural importance
        - explanatory value
        """

        if not sentences:

            return []

        scored: list[
            tuple[float, int, str]
        ] = []

        total = len(sentences)

        for index, sentence in enumerate(
            sentences
        ):

            score = 0.0

            lowered = sentence.lower()

            # ------------------------------------------------
            # Position
            # ------------------------------------------------

            if index == 0:

                score += 4.0

            elif index == 1:

                score += 2.0

            # ------------------------------------------------
            # Ending summary/conclusion
            # ------------------------------------------------

            if index == total - 1:

                score += 2.5

            # ------------------------------------------------
            # Important language
            # ------------------------------------------------

            important_terms = (
                "important",
                "key",
                "main",
                "because",
                "therefore",
                "means",
                "allows",
                "used",
                "works",
                "purpose",
                "result",
                "benefit",
                "difference",
                "essential",
                "typically",
                "overall",
                "in short",
            )

            for term in important_terms:

                if term in lowered:

                    score += 1.5

            # ------------------------------------------------
            # Response-specific signals
            # ------------------------------------------------

            if response_type == ResponseType.DEFINITION:

                if (
                    " is " in lowered
                    or " means " in lowered
                ):

                    score += 4.0

            elif response_type == ResponseType.STEPS:

                if re.search(
                    r"\b(step|first|then|next|finally)\b",
                    lowered,
                ):

                    score += 2.0

            elif response_type == ResponseType.COMPARISON:

                if any(
                    word in lowered
                    for word in (
                        "while",
                        "whereas",
                        "difference",
                        "unlike",
                    )
                ):

                    score += 2.0

            # ------------------------------------------------
            # Avoid uselessly short fragments.
            # ------------------------------------------------

            word_count = (
                self._word_count(
                    sentence
                )
            )

            if word_count < 5:

                score -= 2.0

            elif 8 <= word_count <= 35:

                score += 1.0

            # ------------------------------------------------
            # Penalize obvious formatting noise.
            # ------------------------------------------------

            if sentence.startswith(
                ("http://", "https://")
            ):

                score -= 5.0

            scored.append(
                (
                    score,
                    index,
                    sentence,
                )
            )

        # ----------------------------------------------------
        # Sort by importance.
        # ----------------------------------------------------

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        selected = scored[
            : self._max_highlights
        ]

        # ----------------------------------------------------
        # Restore natural response order.
        # ----------------------------------------------------

        selected.sort(
            key=lambda item: item[1]
        )

        return [
            sentence
            for _, _, sentence
            in selected
        ]

    # ========================================================
    # SPEECH SUMMARY
    # ========================================================

    def _build_speech_summary(
        self,
        highlights: list[str],
        response_type: ResponseType,
    ) -> str:
        """
        Convert selected highlights into natural speech.

        No generic boilerplate is inserted here.

        The speech should sound like an actual assistant
        explaining the important information.
        """

        if not highlights:

            return ""

        text = " ".join(
            highlights
        )

        # ----------------------------------------------------
        # Clean common markdown artifacts.
        # ----------------------------------------------------

        text = (
            self._clean_for_speech(
                text
            )
        )

        return text.strip()

    # ========================================================
    # SPEECH LENGTH LIMIT
    # ========================================================

    def _limit_speech_length(
        self,
        text: str,
    ) -> str:
        """
        Keep speech concise without cutting a sentence
        in the middle.
        """

        if not text:

            return ""

        words = text.split()

        if (
            len(words)
            <= self._speech_word_limit
        ):

            return text

        sentences = (
            self._split_sentences(
                text
            )
        )

        selected = []

        count = 0

        for sentence in sentences:

            sentence_words = (
                len(sentence.split())
            )

            if (
                selected
                and count + sentence_words
                > self._speech_word_limit
            ):

                break

            selected.append(
                sentence
            )

            count += sentence_words

        if selected:

            return " ".join(
                selected
            ).strip()

        return " ".join(
            words[
                : self._speech_word_limit
            ]
        ).strip()

    # ========================================================
    # TEXT CLEANING
    # ========================================================

    def _clean_for_analysis(
        self,
        text: str,
    ) -> str:
        """
        Remove structures that are not useful for
        semantic analysis.
        """

        text = (
            self.CODE_BLOCK_PATTERN.sub(
                " ",
                text,
            )
        )

        text = (
            self.MARKDOWN_LINK_PATTERN.sub(
                r"\1",
                text,
            )
        )

        text = (
            self.MARKDOWN_HEADING_PATTERN.sub(
                "",
                text,
            )
        )

        text = (
            self.BULLET_PATTERN.sub(
                "",
                text,
            )
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    def _clean_for_speech(
        self,
        text: str,
    ) -> str:
        """
        Convert assistant output into speech-friendly text.
        """

        # ----------------------------------------------------
        # Remove fenced code.
        # ----------------------------------------------------

        text = (
            self.CODE_BLOCK_PATTERN.sub(
                "",
                text,
            )
        )

        # ----------------------------------------------------
        # Markdown links → visible label.
        # ----------------------------------------------------

        text = (
            self.MARKDOWN_LINK_PATTERN.sub(
                r"\1",
                text,
            )
        )

        # ----------------------------------------------------
        # Inline code.
        # ----------------------------------------------------

        text = (
            self.INLINE_CODE_PATTERN.sub(
                r"\1",
                text,
            )
        )

        # ----------------------------------------------------
        # Markdown headings.
        # ----------------------------------------------------

        text = (
            self.MARKDOWN_HEADING_PATTERN.sub(
                "",
                text,
            )
        )

        # ----------------------------------------------------
        # Bullets.
        # ----------------------------------------------------

        text = (
            self.BULLET_PATTERN.sub(
                "",
                text,
            )
        )

        # ----------------------------------------------------
        # Remove excessive whitespace.
        # ----------------------------------------------------

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ========================================================
    # UTILITIES
    # ========================================================

    @staticmethod
    def _word_count(
        text: str,
    ) -> int:

        if not text:

            return 0

        return len(
            re.findall(
                r"\b[\w'-]+\b",
                text,
            )
        )

    def _estimate_speech_duration(
        self,
        text: str,
    ) -> float:
        """
        Estimate speech duration in seconds.
        """

        words = self._word_count(
            text
        )

        if words == 0:

            return 0.0

        return (
            words
            / self.WORDS_PER_MINUTE
            * 60.0
        )

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