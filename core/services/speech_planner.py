"""
Krakken AI Speech Planner.

Plans how an AI response should be spoken aloud.

The SpeechPlanner sits between semantic response analysis and
the TTS pipeline.

Architecture:

    Complete AI Response
            ↓
    ResponseIntelligence
            ↓
      ResponseAnalysis
            ↓
       SpeechPlanner
            ↓
        SpeechPlan
            ↓
        TTS Queue
            ↓
       TTS Provider
            ↓
       Audio Player

The planner does NOT:

- synthesize speech
- play audio
- access audio devices
- contain Qt/QML code
- publish EventBus events
- perform semantic response analysis
- call AI providers
- modify the original AI response

Its responsibility is to convert an analyzed response into a
deterministic, TTS-friendly speech plan.

The complete AI response remains untouched.

For example:

    AI response
        ↓
    "The answer is 42.

     There are three important reasons:
     1. ...
     2. ...
     3. ...

     Here is a detailed explanation..."

may become:

    SpeechPlan
        ↓
    [
        "The answer is 42.",
        "There are three important reasons.",
        "First, ...",
        "Second, ...",
        "Third, ..."
    ]

The TTS layer can then process these chunks independently.

Design goals:

- natural speech
- predictable chunk boundaries
- reasonable chunk sizes
- preservation of important information
- avoidance of markdown noise
- avoidance of code being spoken unnecessarily
- clean handling of lists
- clean handling of headings
- safe fallback behavior
- deterministic output
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class SpeechChunkType(str, Enum):
    """
    Classification of a speech chunk.

    This classification is metadata only.

    The TTS provider does not need to understand the semantic
    meaning of a chunk, but the metadata can be useful for
    debugging, future voice controls, or UI state.
    """

    INTRO = "intro"

    SENTENCE = "sentence"

    LIST_ITEM = "list_item"

    HEADING = "heading"

    EMPHASIS = "emphasis"

    CONCLUSION = "conclusion"

    FALLBACK = "fallback"


@dataclass(slots=True)
class SpeechChunk:
    """
    One unit of text intended for speech synthesis.

    A chunk should normally represent one natural spoken unit.

    The planner guarantees that empty chunks are not returned.
    """

    text: str

    chunk_type: SpeechChunkType = (
        SpeechChunkType.SENTENCE
    )

    priority: int = 1

    source_index: int = 0

    estimated_words: int = 0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.text = self.text.strip()

        if self.estimated_words <= 0:
            self.estimated_words = len(
                self.text.split()
            )


@dataclass(slots=True)
class SpeechPlan:
    """
    Complete speech plan for one AI response.

    `chunks` contains the actual speech units.

    `speech_text` contains the final text represented by those
    chunks.

    `estimated_words` and `estimated_seconds` are intentionally
    approximate. They are planning values, not audio measurements.
    """

    chunks: list[SpeechChunk]

    speech_text: str

    estimated_words: int

    estimated_seconds: float

    source_length: int

    source_word_count: int

    truncated: bool = False

    used_fallback: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def is_empty(self) -> bool:
        """Return True when the plan contains no speech."""

        return not self.chunks

    @property
    def chunk_count(self) -> int:
        """Return the number of speech chunks."""

        return len(self.chunks)


class SpeechPlanner:
    """
    Convert response analysis into a TTS-ready speech plan.

    The planner intentionally remains independent from:

    - TTSProvider
    - AudioPlayer
    - EventBus
    - Qt/QML
    - AI providers

    It only plans speech.
    """

    # ==========================================================
    # CONFIGURATION
    # ==========================================================

    DEFAULT_WORDS_PER_MINUTE = 145.0

    DEFAULT_MAX_WORDS = 180

    DEFAULT_MAX_CHUNK_WORDS = 38

    DEFAULT_MIN_CHUNK_WORDS = 2

    DEFAULT_MAX_SENTENCE_LENGTH = 240

    # Markdown/code patterns.

    _CODE_FENCE_RE = re.compile(
        r"```[\s\S]*?```",
        re.MULTILINE,
    )

    _INLINE_CODE_RE = re.compile(
        r"`([^`]+)`"
    )

    _MARKDOWN_LINK_RE = re.compile(
        r"\[([^\]]+)\]\([^)]+\)"
    )

    _MARKDOWN_IMAGE_RE = re.compile(
        r"!\[([^\]]*)\]\([^)]+\)"
    )

    _BOLD_RE = re.compile(
        r"\*\*(.*?)\*\*"
    )

    _ITALIC_RE = re.compile(
        r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)"
    )

    _UNDERLINE_RE = re.compile(
        r"__(.*?)__"
    )

    _HEADING_RE = re.compile(
        r"^\s{0,3}#{1,6}\s+(.+?)\s*$"
    )

    _BULLET_RE = re.compile(
        r"^\s*(?:[-*•▪◦])\s+(.+?)\s*$"
    )

    _NUMBERED_LIST_RE = re.compile(
        r"^\s*\d+[.)]\s+(.+?)\s*$"
    )

    _BLOCKQUOTE_RE = re.compile(
        r"^\s*>\s?(.*)$"
    )

    _HORIZONTAL_RULE_RE = re.compile(
        r"^\s*(?:[-*_]\s*){3,}$"
    )

    # Sentence terminators.

    _SENTENCE_TERMINATORS = (
        ".",
        "!",
        "?",
        "。",
        "！",
        "？",
    )

    # Characters that usually create awkward speech.

    _UNSPEAKABLE_MARKDOWN = (
        "###",
        "##",
        "#",
        "---",
        "***",
    )

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        logger: Any = None,
        words_per_minute: float = DEFAULT_WORDS_PER_MINUTE,
        max_words: int = DEFAULT_MAX_WORDS,
        max_chunk_words: int = DEFAULT_MAX_CHUNK_WORDS,
        min_chunk_words: int = DEFAULT_MIN_CHUNK_WORDS,
        max_sentence_length: int = DEFAULT_MAX_SENTENCE_LENGTH,
    ) -> None:

        self._logger = logger

        self._words_per_minute = max(
            60.0,
            float(words_per_minute),
        )

        self._max_words = max(
            1,
            int(max_words),
        )

        self._max_chunk_words = max(
            1,
            int(max_chunk_words),
        )

        self._min_chunk_words = max(
            1,
            int(min_chunk_words),
        )

        self._max_sentence_length = max(
            20,
            int(max_sentence_length),
        )

        self._log(
            "SpeechPlanner initialized."
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def plan(
        self,
        speech_text: str,
        *,
        response_type: Any = None,
        is_long_response: bool = False,
        should_use_summary: bool = False,
        highlights: Iterable[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpeechPlan:
        """
        Create a speech plan from selected speech text.

        `speech_text` should normally already be selected by
        ResponseIntelligence.

        The planner does NOT decide what information is important.

        It only decides how the selected information should be
        converted into natural speech chunks.

        Parameters
        ----------
        speech_text:
            Text selected for speech.

        response_type:
            Optional response classification metadata.

        is_long_response:
            Whether the original response was considered long.

        should_use_summary:
            Whether ResponseIntelligence selected summary mode.

        highlights:
            Optional semantic highlights.

        metadata:
            Optional upstream metadata.
        """

        original_text = (
            speech_text
            if isinstance(speech_text, str)
            else ""
        )

        original_text = original_text.strip()

        source_length = len(
            original_text
        )

        source_word_count = self._word_count(
            original_text
        )

        if not original_text:

            return SpeechPlan(
                chunks=[],
                speech_text="",
                estimated_words=0,
                estimated_seconds=0.0,
                source_length=source_length,
                source_word_count=source_word_count,
                metadata={
                    "empty": True,
                },
            )

        # ------------------------------------------------------
        # CLEAN SPEECH TEXT
        # ------------------------------------------------------

        cleaned = self._clean_text(
            original_text
        )

        if not cleaned:

            return SpeechPlan(
                chunks=[],
                speech_text="",
                estimated_words=0,
                estimated_seconds=0.0,
                source_length=source_length,
                source_word_count=source_word_count,
                metadata={
                    "empty_after_cleaning": True,
                },
            )

        # ------------------------------------------------------
        # SPLIT INTO STRUCTURAL UNITS
        # ------------------------------------------------------

        units = self._extract_units(
            cleaned
        )

        # ------------------------------------------------------
        # BUILD SPEECH CHUNKS
        # ------------------------------------------------------

        chunks = self._build_chunks(
            units
        )

        # ------------------------------------------------------
        # REMOVE EMPTY CHUNKS
        # ------------------------------------------------------

        chunks = [
            chunk
            for chunk in chunks
            if chunk.text.strip()
        ]

        # ------------------------------------------------------
        # LIMIT SPEECH
        # ------------------------------------------------------

        truncated = False

        if self._word_count_from_chunks(
            chunks
        ) > self._max_words:

            chunks = self._limit_chunks(
                chunks
            )

            truncated = True

        # ------------------------------------------------------
        # FALLBACK
        # ------------------------------------------------------

        used_fallback = False

        if not chunks:

            fallback_text = (
                self._fallback_text(
                    cleaned
                )
            )

            if fallback_text:

                chunks = [
                    SpeechChunk(
                        text=fallback_text,
                        chunk_type=(
                            SpeechChunkType.FALLBACK
                        ),
                        priority=1,
                        source_index=0,
                    )
                ]

                used_fallback = True

        # ------------------------------------------------------
        # FINAL SPEECH TEXT
        # ------------------------------------------------------

        final_text = self._join_chunks(
            chunks
        )

        estimated_words = self._word_count(
            final_text
        )

        estimated_seconds = (
            estimated_words
            / self._words_per_minute
            * 60.0
        )

        result_metadata = dict(
            metadata or {}
        )

        result_metadata.update(
            {
                "response_type": (
                    self._enum_value(
                        response_type
                    )
                ),
                "is_long_response": (
                    is_long_response
                ),
                "should_use_summary": (
                    should_use_summary
                ),
                "highlight_count": (
                    len(list(highlights or []))
                ),
                "planner_max_words": (
                    self._max_words
                ),
                "planner_max_chunk_words": (
                    self._max_chunk_words
                ),
            }
        )

        plan = SpeechPlan(
            chunks=chunks,
            speech_text=final_text,
            estimated_words=estimated_words,
            estimated_seconds=estimated_seconds,
            source_length=source_length,
            source_word_count=source_word_count,
            truncated=truncated,
            used_fallback=used_fallback,
            metadata=result_metadata,
        )

        self._log(
            "Speech plan created: "
            f"chunks={plan.chunk_count}, "
            f"words={plan.estimated_words}, "
            f"seconds={plan.estimated_seconds:.1f}, "
            f"truncated={plan.truncated}, "
            f"fallback={plan.used_fallback}"
        )

        return plan

    # ==========================================================
    # RESPONSE ANALYSIS INTEGRATION
    # ==========================================================

    def plan_from_analysis(
        self,
        analysis: Any,
    ) -> SpeechPlan:
        """
        Create a SpeechPlan directly from a ResponseAnalysis.

        This is the preferred integration point for
        AssistantService.

        The method deliberately accesses only the fields that
        ResponseAnalysis is expected to expose.
        """

        speech_text = getattr(
            analysis,
            "speech_text",
            "",
        )

        response_type = getattr(
            analysis,
            "response_type",
            None,
        )

        is_long_response = bool(
            getattr(
                analysis,
                "is_long_response",
                False,
            )
        )

        should_use_summary = bool(
            getattr(
                analysis,
                "should_use_summary",
                False,
            )
        )

        highlights = getattr(
            analysis,
            "highlights",
            [],
        )

        metadata = getattr(
            analysis,
            "metadata",
            None,
        )

        return self.plan(
            speech_text,
            response_type=response_type,
            is_long_response=is_long_response,
            should_use_summary=should_use_summary,
            highlights=highlights,
            metadata=metadata,
        )

    # ==========================================================
    # TEXT CLEANING
    # ==========================================================

    def _clean_text(
        self,
        text: str,
    ) -> str:
        """
        Convert Markdown-heavy AI output into speech-friendly
        plain text.

        Code blocks are intentionally removed.

        The planner is not a Markdown renderer. It only removes
        syntax that would sound bad when spoken.
        """

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        # ------------------------------------------------------
        # Remove code blocks.
        #
        # Speaking an entire source-code block is usually
        # undesirable. Code should remain available visually.
        # ------------------------------------------------------

        text = self._CODE_FENCE_RE.sub(
            "",
            text,
        )

        # ------------------------------------------------------
        # Remove Markdown images.
        # ------------------------------------------------------

        text = self._MARKDOWN_IMAGE_RE.sub(
            "",
            text,
        )

        # ------------------------------------------------------
        # Convert Markdown links to visible link text.
        # ------------------------------------------------------

        text = self._MARKDOWN_LINK_RE.sub(
            r"\1",
            text,
        )

        # ------------------------------------------------------
        # Remove inline-code markers but preserve the content.
        # ------------------------------------------------------

        text = self._INLINE_CODE_RE.sub(
            r"\1",
            text,
        )

        # ------------------------------------------------------
        # Remove common emphasis markers.
        # ------------------------------------------------------

        text = self._BOLD_RE.sub(
            r"\1",
            text,
        )

        text = self._ITALIC_RE.sub(
            r"\1",
            text,
        )

        text = self._UNDERLINE_RE.sub(
            r"\1",
            text,
        )

        # ------------------------------------------------------
        # Normalize whitespace.
        # ------------------------------------------------------

        lines: list[str] = []

        for raw_line in text.split("\n"):

            line = raw_line.strip()

            if not line:
                continue

            if self._HORIZONTAL_RULE_RE.match(
                line
            ):
                continue

            # Remove blockquote marker.

            blockquote = (
                self._BLOCKQUOTE_RE.match(
                    line
                )
            )

            if blockquote:

                line = (
                    blockquote.group(1)
                    .strip()
                )

            # Remove heading markers.

            heading = (
                self._HEADING_RE.match(
                    line
                )
            )

            if heading:

                line = (
                    heading.group(1)
                    .strip()
                )

            # Convert bullets into plain speech text.

            bullet = (
                self._BULLET_RE.match(
                    line
                )
            )

            if bullet:

                line = (
                    bullet.group(1)
                    .strip()
                )

            # Convert numbered list markers.

            numbered = (
                self._NUMBERED_LIST_RE.match(
                    line
                )
            )

            if numbered:

                line = (
                    numbered.group(1)
                    .strip()
                )

            if not line:
                continue

            lines.append(
                line
            )

        cleaned = "\n".join(
            lines
        )

        # Remove repeated whitespace.

        cleaned = re.sub(
            r"[ \t]+",
            " ",
            cleaned,
        )

        # Avoid excessive blank lines.

        cleaned = re.sub(
            r"\n{3,}",
            "\n\n",
            cleaned,
        )

        return cleaned.strip()

    # ==========================================================
    # UNIT EXTRACTION
    # ==========================================================

    def _extract_units(
        self,
        text: str,
    ) -> list[tuple[str, SpeechChunkType]]:
        """
        Convert cleaned text into structural speech units.

        Each paragraph is processed independently.

        Lists are treated as separate spoken units.
        """

        units: list[
            tuple[str, SpeechChunkType]
        ] = []

        paragraphs = re.split(
            r"\n{2,}",
            text,
        )

        for paragraph in paragraphs:

            paragraph = paragraph.strip()

            if not paragraph:
                continue

            lines = [
                line.strip()
                for line in paragraph.split("\n")
                if line.strip()
            ]

            # --------------------------------------------------
            # Handle individual list lines.
            # --------------------------------------------------

            for line in lines:

                list_match = (
                    self._BULLET_RE.match(
                        line
                    )
                )

                numbered_match = (
                    self._NUMBERED_LIST_RE.match(
                        line
                    )
                )

                if list_match:

                    content = (
                        list_match.group(1)
                        .strip()
                    )

                    if content:

                        units.append(
                            (
                                content,
                                SpeechChunkType.LIST_ITEM,
                            )
                        )

                    continue

                if numbered_match:

                    content = (
                        numbered_match.group(1)
                        .strip()
                    )

                    if content:

                        units.append(
                            (
                                content,
                                SpeechChunkType.LIST_ITEM,
                            )
                        )

                    continue

            # --------------------------------------------------
            # If paragraph consists of list items, the list
            # items above are sufficient.
            # --------------------------------------------------

            if all(
                self._is_list_line(line)
                for line in lines
            ):

                continue

            # --------------------------------------------------
            # Normal paragraph.
            # --------------------------------------------------

            paragraph_text = " ".join(
                lines
            )

            sentence_units = (
                self._split_sentences(
                    paragraph_text
                )
            )

            for sentence in sentence_units:

                sentence = sentence.strip()

                if not sentence:
                    continue

                chunk_type = (
                    SpeechChunkType.SENTENCE
                )

                if self._looks_like_conclusion(
                    sentence
                ):

                    chunk_type = (
                        SpeechChunkType.CONCLUSION
                    )

                units.append(
                    (
                        sentence,
                        chunk_type,
                    )
                )

        return units

    # ==========================================================
    # SENTENCE SPLITTING
    # ==========================================================

    def _split_sentences(
        self,
        text: str,
    ) -> list[str]:
        """
        Split text into natural sentence units.

        This is intentionally conservative.

        It avoids blindly splitting on every period because
        periods may occur inside:

        - URLs
        - decimal numbers
        - abbreviations
        - file names
        - technical identifiers
        """

        text = text.strip()

        if not text:
            return []

        # ------------------------------------------------------
        # Protect common technical patterns.
        # ------------------------------------------------------

        protected: dict[str, str] = {}

        def protect(
            match: re.Match[str],
        ) -> str:

            token = (
                f"__KRK_SENTENCE_{len(protected)}__"
            )

            protected[token] = match.group(0)

            return token

        # URLs.

        text = re.sub(
            r"https?://\S+",
            protect,
            text,
        )

        # Decimal numbers.

        text = re.sub(
            r"\b\d+\.\d+\b",
            protect,
            text,
        )

        # File extensions.

        text = re.sub(
            r"\b[\w.-]+\.(?:py|js|ts|tsx|jsx|json|yaml|yml|txt|md|cpp|rs|java)\b",
            protect,
            text,
            flags=re.IGNORECASE,
        )

        # ------------------------------------------------------
        # Split at sentence-ending punctuation followed by
        # whitespace and an uppercase/numeric/opening character.
        # ------------------------------------------------------

        parts = re.split(
            r"(?<=[.!?。！？])\s+(?=[A-Z0-9\"“‘(\[])",
            text,
        )

        # ------------------------------------------------------
        # Restore protected content.
        # ------------------------------------------------------

        restored: list[str] = []

        for part in parts:

            for token, value in protected.items():

                part = part.replace(
                    token,
                    value,
                )

            restored.append(
                part.strip()
            )

        # ------------------------------------------------------
        # Handle sentences that are excessively long.
        # ------------------------------------------------------

        result: list[str] = []

        for sentence in restored:

            if (
                len(sentence)
                <= self._max_sentence_length
            ):

                result.append(
                    sentence
                )

                continue

            result.extend(
                self._split_long_sentence(
                    sentence
                )
            )

        return [
            sentence
            for sentence in result
            if sentence
        ]

    # ==========================================================
    # LONG SENTENCE SPLITTING
    # ==========================================================

    def _split_long_sentence(
        self,
        sentence: str,
    ) -> list[str]:
        """
        Break an excessively long sentence at natural
        punctuation before falling back to word boundaries.
        """

        sentence = sentence.strip()

        if not sentence:
            return []

        # First try commas, semicolons and colons.

        parts = re.split(
            r"(?<=[,;:])\s+",
            sentence,
        )

        if len(parts) > 1:

            result: list[str] = []

            current = ""

            for part in parts:

                part = part.strip()

                if not part:
                    continue

                candidate = (
                    f"{current} {part}".strip()
                )

                if (
                    len(candidate)
                    <= self._max_sentence_length
                ):

                    current = candidate

                else:

                    if current:

                        result.append(
                            current
                        )

                    current = part

            if current:

                result.append(
                    current
                )

            if result:

                return result

        # ------------------------------------------------------
        # Final fallback: word-boundary split.
        # ------------------------------------------------------

        words = sentence.split()

        result = []

        current_words: list[str] = []

        current_length = 0

        for word in words:

            additional = (
                len(word)
                + (
                    1
                    if current_words
                    else 0
                )
            )

            if (
                current_words
                and
                current_length
                + additional
                > self._max_sentence_length
            ):

                result.append(
                    " ".join(
                        current_words
                    )
                )

                current_words = []

                current_length = 0

            current_words.append(
                word
            )

            current_length += additional

        if current_words:

            result.append(
                " ".join(
                    current_words
                )
            )

        return result

    # ==========================================================
    # CHUNK BUILDING
    # ==========================================================

    def _build_chunks(
        self,
        units: list[
            tuple[str, SpeechChunkType]
        ],
    ) -> list[SpeechChunk]:
        """
        Convert structural units into TTS-sized chunks.

        Short neighboring sentences are grouped when possible.

        Long sentences are kept independent.
        """

        chunks: list[SpeechChunk] = []

        current_text: list[str] = []

        current_words = 0

        current_type = (
            SpeechChunkType.SENTENCE
        )

        source_index = 0

        def flush() -> None:

            nonlocal current_text
            nonlocal current_words
            nonlocal current_type
            nonlocal source_index

            if not current_text:
                return

            text = " ".join(
                current_text
            ).strip()

            if text:

                chunks.append(
                    SpeechChunk(
                        text=text,
                        chunk_type=current_type,
                        priority=(
                            self._priority_for_type(
                                current_type
                            )
                        ),
                        source_index=source_index,
                    )
                )

                source_index += 1

            current_text = []

            current_words = 0

        for text, chunk_type in units:

            text = text.strip()

            if not text:
                continue

            word_count = self._word_count(
                text
            )

            # --------------------------------------------------
            # List items should normally remain separate.
            # --------------------------------------------------

            if (
                chunk_type
                == SpeechChunkType.LIST_ITEM
            ):

                flush()

                chunks.append(
                    SpeechChunk(
                        text=text,
                        chunk_type=chunk_type,
                        priority=(
                            self._priority_for_type(
                                chunk_type
                            )
                        ),
                        source_index=source_index,
                        estimated_words=word_count,
                    )
                )

                source_index += 1

                continue

            # --------------------------------------------------
            # Conclusion gets its own chunk.
            # --------------------------------------------------

            if (
                chunk_type
                == SpeechChunkType.CONCLUSION
            ):

                flush()

                chunks.append(
                    SpeechChunk(
                        text=text,
                        chunk_type=chunk_type,
                        priority=(
                            self._priority_for_type(
                                chunk_type
                            )
                        ),
                        source_index=source_index,
                        estimated_words=word_count,
                    )
                )

                source_index += 1

                continue

            # --------------------------------------------------
            # If one sentence is already large, do not merge it.
            # --------------------------------------------------

            if (
                word_count
                >= self._max_chunk_words
            ):

                flush()

                chunks.append(
                    SpeechChunk(
                        text=text,
                        chunk_type=chunk_type,
                        priority=(
                            self._priority_for_type(
                                chunk_type
                            )
                        ),
                        source_index=source_index,
                        estimated_words=word_count,
                    )
                )

                source_index += 1

                continue

            # --------------------------------------------------
            # Try to merge short neighboring sentences.
            # --------------------------------------------------

            if (
                current_words
                + word_count
                + (
                    1
                    if current_words
                    else 0
                )
                <= self._max_chunk_words
            ):

                current_text.append(
                    text
                )

                current_words += (
                    word_count
                    + (
                        1
                        if current_words
                        else 0
                    )
                )

                if not current_text:

                    current_type = (
                        chunk_type
                    )

            else:

                flush()

                current_type = (
                    chunk_type
                )

                current_text.append(
                    text
                )

                current_words = (
                    word_count
                )

        flush()

        return chunks

    # ==========================================================
    # CHUNK LIMITING
    # ==========================================================

    def _limit_chunks(
        self,
        chunks: list[SpeechChunk],
    ) -> list[SpeechChunk]:
        """
        Limit the total amount of speech.

        This method does NOT perform semantic ranking.

        It preserves order and prefers to keep:

        - early content
        - conclusions
        - higher-priority chunk types

        The actual semantic selection should already have been
        performed by ResponseIntelligence.
        """

        if not chunks:
            return []

        selected: list[SpeechChunk] = []

        total_words = 0

        # ------------------------------------------------------
        # First pass: normal ordered content.
        # ------------------------------------------------------

        for chunk in chunks:

            words = chunk.estimated_words

            if (
                total_words + words
                <= self._max_words
            ):

                selected.append(
                    chunk
                )

                total_words += words

                continue

            # --------------------------------------------------
            # Try to preserve an important conclusion.
            # --------------------------------------------------

            if (
                chunk.chunk_type
                == SpeechChunkType.CONCLUSION
            ):

                selected.append(
                    chunk
                )

            break

        # ------------------------------------------------------
        # Deduplicate if conclusion was already included.
        # ------------------------------------------------------

        unique: list[SpeechChunk] = []

        seen: set[int] = set()

        for chunk in selected:

            identity = id(chunk)

            if identity in seen:
                continue

            seen.add(identity)

            unique.append(
                chunk
            )

        return unique

    # ==========================================================
    # FALLBACK
    # ==========================================================

    def _fallback_text(
        self,
        text: str,
    ) -> str:
        """
        Produce a safe fallback speech string.

        This is intentionally simple and deterministic.
        """

        text = text.strip()

        if not text:
            return ""

        # Remove obvious Markdown syntax.

        text = re.sub(
            r"[#*_`]",
            "",
            text,
        )

        # Collapse whitespace.

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        words = text.split()

        if (
            len(words)
            > self._max_words
        ):

            words = words[
                :self._max_words
            ]

        return " ".join(
            words
        ).strip()

    # ==========================================================
    # TYPE CLASSIFICATION
    # ==========================================================

    @staticmethod
    def _priority_for_type(
        chunk_type: SpeechChunkType,
    ) -> int:
        """
        Return a simple planning priority.

        Higher values indicate information that should be
        preserved preferentially if future planning layers need
        to trim speech.

        Semantic ranking still belongs to ResponseIntelligence.
        """

        priorities = {
            SpeechChunkType.CONCLUSION: 5,
            SpeechChunkType.INTRO: 4,
            SpeechChunkType.EMPHASIS: 4,
            SpeechChunkType.SENTENCE: 3,
            SpeechChunkType.LIST_ITEM: 2,
            SpeechChunkType.HEADING: 2,
            SpeechChunkType.FALLBACK: 1,
        }

        return priorities.get(
            chunk_type,
            1,
        )

    @staticmethod
    def _looks_like_conclusion(
        text: str,
    ) -> bool:
        """
        Detect common conclusion language.

        This is intentionally lightweight.

        It does not determine semantic importance.
        """

        lowered = text.lower().strip()

        prefixes = (
            "in conclusion",
            "overall",
            "to summarize",
            "to sum up",
            "the key point",
            "the main point",
            "bottom line",
            "ultimately",
            "so the answer is",
            "therefore",
        )

        return lowered.startswith(
            prefixes
        )

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _is_list_line(
        line: str,
    ) -> bool:
        """
        Return True when a line is a bullet or numbered item.
        """

        return bool(
            SpeechPlanner._BULLET_RE.match(
                line
            )
            or SpeechPlanner._NUMBERED_LIST_RE.match(
                line
            )
        )

    @staticmethod
    def _word_count(
        text: str,
    ) -> int:
        """
        Count words in a text string.
        """

        if not text:
            return 0

        return len(
            text.split()
        )

    @staticmethod
    def _word_count_from_chunks(
        chunks: list[SpeechChunk],
    ) -> int:
        """
        Count words across chunks.
        """

        return sum(
            chunk.estimated_words
            for chunk in chunks
        )

    @staticmethod
    def _join_chunks(
        chunks: list[SpeechChunk],
    ) -> str:
        """
        Join speech chunks into one readable speech string.
        """

        return " ".join(
            chunk.text.strip()
            for chunk in chunks
            if chunk.text.strip()
        ).strip()

    @staticmethod
    def _enum_value(
        value: Any,
    ) -> Any:
        """
        Safely convert Enum-like values to their serialized
        value.
        """

        if value is None:
            return None

        return getattr(
            value,
            "value",
            value,
        )

    # ==========================================================
    # ITERATION
    # ==========================================================

    def iter_chunks(
        self,
        plan: SpeechPlan,
    ) -> Iterable[SpeechChunk]:
        """
        Iterate through planned speech chunks.

        Keeping this method here makes the TTS integration
        explicit and avoids exposing internal list assumptions.
        """

        yield from plan.chunks

    # ==========================================================
    # LOGGING
    # ==========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:
        """
        Safely write to the configured logger.
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

            pass