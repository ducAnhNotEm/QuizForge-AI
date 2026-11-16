"""
Pydantic Schemas and Contract Adapters for QuizForge-AI.
Milestone: M1 (API Contract & Schema Mapping - Enhanced with Bloom's Taxonomy)

This module defines:
1. Target Question Schema: Standard MCQ schema used by QuizForge-AI,
   incorporating Bloom's Cognitive Taxonomy and Difficulty Levels.
2. Adapter functions between QuestGen-AI-Agent format and the target format
   (``questgen_to_target_schema`` and the lossy reverse ``target_to_questgen``).
3. Hand-off schemas between ingestion, retrieval and generation.
4. Learner-model schemas (attempts, concept mastery) for adaptive quizzes.

Pure parsing rules live in ``backend.mcq_parsing`` so they can be tested
without Pydantic.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from backend.mcq_parsing import (
    OPTION_LABELS,
    canon_text,
    has_positional_option,
    make_snippet,
    resolve_correct_index,
    shuffled_order,
    strip_option_labels,
)

logger = logging.getLogger(__name__)

MIN_QUESTION_CHARS = 10
MIN_EXPLANATION_CHARS = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_option_id(value: Any) -> Any:
    """Normalize " b " -> "B" *at parse time* so stored values are canonical.

    Non-strings are returned untouched so Pydantic reports a clear type error.
    """
    if isinstance(value, str):
        return value.strip().upper()
    return value


# "A" | "B" | "C" | "D", normalized before validation.
OptionId = Annotated[Literal["A", "B", "C", "D"], BeforeValidator(_normalize_option_id)]


class QuestionStatus(str, Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class BloomLevel(str, Enum):
    REMEMBER = "remember"       # Nhận biết / Ghi nhớ
    UNDERSTAND = "understand"   # Thông hiểu
    APPLY = "apply"             # Vận dụng
    ANALYZE = "analyze"         # Phân tích
    EVALUATE = "evaluate"       # Đánh giá
    CREATE = "create"           # Sáng tạo


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class OptionItem(BaseModel):
    id: OptionId = Field(description="Option identifier: 'A', 'B', 'C' or 'D' (normalized)")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="Option display text"
    )


class SourceReference(BaseModel):
    doc_id: str = Field(description="Associated document ID")
    file_name: str = Field(description="Original file name")
    page: Optional[int] = Field(default=None, description="Page number if available, otherwise null")
    snippet: str = Field(description="Relevant extracted text segment")
    chunk_id: Optional[str] = Field(
        default=None,
        description="ID of the DocumentChunk this reference was taken from, if known",
    )


class TargetMCQuestion(BaseModel):
    # Re-run validators on assignment so `q.status = ACCEPTED` cannot bypass
    # the "accepted questions need a source" rule.
    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(description="Unique question identifier")
    course_id: str = Field(description="Target course ID")
    type: Literal["mcq"] = Field(default="mcq", description="Question type, always 'mcq'")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="Difficulty level of the question ('easy', 'medium', 'hard')",
    )
    bloom_level: BloomLevel = Field(
        default=BloomLevel.UNDERSTAND,
        description="Bloom's cognitive taxonomy level: remember, understand, apply, analyze, evaluate, create",
    )
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=MIN_QUESTION_CHARS)
    ] = Field(description="The main question prompt (stem)")
    options: list[OptionItem] = Field(
        min_length=4,
        max_length=4,
        description="Exactly 4 unique options (A, B, C, D)",
    )
    correct_option_id: OptionId = Field(description="ID of the correct option: 'A', 'B', 'C' or 'D'")
    explanation: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=MIN_EXPLANATION_CHARS)
    ] = Field(description="Clear rationale explaining the correct answer")
    source_refs: list[SourceReference] = Field(
        default_factory=list,
        description="Evidence excerpts supporting the question (required once ACCEPTED)",
    )
    status: QuestionStatus = Field(
        default=QuestionStatus.DRAFT,
        description="Review status of the question",
    )
    # --- provenance / adaptivity metadata (all optional) ---
    concept_ids: list[str] = Field(
        default_factory=list, description="Concepts this question assesses"
    )
    generator_model: Optional[str] = Field(default=None, description="Model that wrote the question")
    prompt_version: Optional[str] = Field(default=None, description="Prompt template version")
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_mcq_integrity(self):
        # 1. Exactly 4 unique option IDs (IDs are already limited to A-D).
        option_ids = [opt.id for opt in self.options]
        if len(set(option_ids)) != 4:
            raise ValueError("MCQ must have exactly 4 unique option IDs (A, B, C, D)")

        # 2. Option texts must be unique (NFC + whitespace + case insensitive).
        option_texts = [canon_text(opt.text) for opt in self.options]
        if len(set(option_texts)) != 4:
            raise ValueError("All 4 option texts must be unique")

        # 3. correct_option_id must reference one of the options.
        if self.correct_option_id not in option_ids:
            raise ValueError(
                f"correct_option_id '{self.correct_option_id}' does not match any option ID {option_ids}"
            )

        # 4. A question can only be accepted if it cites real evidence.
        if self.status == QuestionStatus.ACCEPTED and not any(
            ref.snippet.strip() for ref in self.source_refs
        ):
            raise ValueError(
                "An ACCEPTED question needs at least one source_ref with a non-empty snippet"
            )
        return self


# ==============================================================================
# Adapter Functions: QuestGen <--> Target Schema
# ==============================================================================

_BLOOM_ALIASES: dict[str, BloomLevel] = {
    "analyse": BloomLevel.ANALYZE,
    "nhận biết": BloomLevel.REMEMBER,
    "ghi nhớ": BloomLevel.REMEMBER,
    "thông hiểu": BloomLevel.UNDERSTAND,
    "vận dụng": BloomLevel.APPLY,
    "phân tích": BloomLevel.ANALYZE,
    "đánh giá": BloomLevel.EVALUATE,
    "sáng tạo": BloomLevel.CREATE,
}

_DIFFICULTY_ALIASES: dict[str, DifficultyLevel] = {
    "moderate": DifficultyLevel.MEDIUM,
    "complex": DifficultyLevel.HARD,
    "dễ": DifficultyLevel.EASY,
    "trung bình": DifficultyLevel.MEDIUM,
    "khó": DifficultyLevel.HARD,
}

_STATUS_ALIASES: dict[str, QuestionStatus] = {
    "pending": QuestionStatus.DRAFT,
    "draft": QuestionStatus.DRAFT,
    "approved": QuestionStatus.ACCEPTED,
    "accepted": QuestionStatus.ACCEPTED,
    "rejected": QuestionStatus.REJECTED,
}


def _coerce_label(
    value: Any,
    enum_cls: type[Enum],
    aliases: dict[str, Enum],
    default: Enum,
    field_name: str,
    strict: bool,
) -> Enum:
    """Map a raw label to an enum member.

    Unknown labels fall back to ``default`` *with a warning* (or raise when
    ``strict``) instead of silently skewing adaptive selection.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, enum_cls):
        return value
    key = canon_text(str(value))
    try:
        return enum_cls(key)
    except ValueError:
        pass
    if key in aliases:
        return aliases[key]
    message = f"Unknown {field_name} {value!r}; expected one of {[m.value for m in enum_cls]}"
    if strict:
        raise ValueError(message)
    logger.warning("%s. Falling back to %r.", message, default.value)
    return default


def questgen_to_target_schema(
    questgen_data: dict[str, Any],
    question_id: str,
    course_id: str,
    source_lookup: Optional[dict[str, dict]] = None,
    status: str = "draft",
    bloom_level: Optional[str] = None,
    difficulty: Optional[str] = None,
    *,
    strict_sources: bool = True,
    strict_labels: bool = False,
    shuffle: bool = True,
    concept_ids: Optional[list[str]] = None,
    generator_model: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> TargetMCQuestion:
    """Transform QuestGen's GeneratedQuestion into a ``TargetMCQuestion``.

    - ``correct_answer`` may be a letter ("B"), "B. text", or the option text.
    - Option texts that all start with "A. ", "B. " ... are stripped of them.
    - Unknown ``source_ids`` raise when ``strict_sources`` (default); otherwise
      they are logged and skipped.
    - Unknown Bloom/difficulty labels log a warning (raise when ``strict_labels``).
    - Options are shuffled deterministically (seeded by ``question_id``) unless
      an option refers to other options ("Cả A và B", "Tất cả các đáp án trên").
    """
    stem = questgen_data.get("stem") or questgen_data.get("question") or ""
    raw_options = questgen_data.get("options") or []
    correct_answer = questgen_data.get("correct_answer") or ""
    explanation = questgen_data.get("explanation") or ""
    source_ids = list(questgen_data.get("source_ids") or [])

    mapped_bloom = _coerce_label(
        bloom_level or questgen_data.get("bloom_level") or questgen_data.get("bloom"),
        BloomLevel, _BLOOM_ALIASES, BloomLevel.UNDERSTAND, "bloom_level", strict_labels,
    )
    mapped_diff = _coerce_label(
        difficulty or questgen_data.get("difficulty"),
        DifficultyLevel, _DIFFICULTY_ALIASES, DifficultyLevel.MEDIUM, "difficulty", strict_labels,
    )

    if not isinstance(raw_options, (list, tuple)) or len(raw_options) != 4:
        count = len(raw_options) if isinstance(raw_options, (list, tuple)) else "invalid"
        raise ValueError(f"QuestGen data must have exactly 4 options, got {count}")

    option_texts = strip_option_labels([str(option) for option in raw_options])
    formatted_options = [
        OptionItem(id=OPTION_LABELS[i], text=option_texts[i]) for i in range(4)
    ]

    correct_index = resolve_correct_index(correct_answer, option_texts)
    if correct_index is None:
        raise ValueError(f"correct_answer {correct_answer!r} not found in options: {option_texts}")
    correct_option_id = OPTION_LABELS[correct_index]

    # Source references.
    source_refs: list[SourceReference] = []
    unresolved: list[str] = []
    for sid in source_ids:
        info = (source_lookup or {}).get(sid)
        if info is None:
            unresolved.append(str(sid))
            continue
        source_refs.append(
            SourceReference(
                doc_id=info.get("doc_id", "doc_unknown"),
                file_name=info.get("file_name", "Unknown File"),
                page=info.get("page"),
                snippet=info.get("snippet", ""),
                chunk_id=info.get("chunk_id"),
            )
        )
    if unresolved:
        message = f"source_ids {unresolved} were not found in source_lookup"
        if strict_sources:
            raise ValueError(message)
        logger.warning("%s; skipping them.", message)

    status_key = canon_text(status)
    if status_key not in _STATUS_ALIASES:
        logger.warning("Unknown status %r; using 'draft'.", status)
    mapped_status = _STATUS_ALIASES.get(status_key, QuestionStatus.DRAFT)

    question = TargetMCQuestion(
        id=question_id,
        course_id=course_id,
        type="mcq",
        difficulty=mapped_diff,
        bloom_level=mapped_bloom,
        question=stem,
        options=formatted_options,
        correct_option_id=correct_option_id,
        explanation=explanation,
        source_refs=source_refs,
        status=mapped_status,
        concept_ids=list(concept_ids or []),
        generator_model=generator_model,
        prompt_version=prompt_version,
    )
    return shuffle_options(question) if shuffle else question


def shuffle_options(
    question: TargetMCQuestion, seed: Optional[Union[int, str]] = None
) -> TargetMCQuestion:
    """Return a copy with options permuted, relabeled A-D, answer remapped.

    Deterministic: the default seed is ``question.id``. Questions whose options
    reference each other ("Cả A và B đều đúng") are returned unchanged.
    """
    if has_positional_option([opt.text for opt in question.options]):
        logger.info("Question %s has position-dependent options; not shuffling.", question.id)
        return question

    order = shuffled_order(4, question.id if seed is None else seed)
    new_options: list[OptionItem] = []
    new_correct: Optional[str] = None
    for new_index, old_index in enumerate(order):
        old = question.options[old_index]
        label = OPTION_LABELS[new_index]
        new_options.append(OptionItem(id=label, text=old.text))
        if old.id == question.correct_option_id:
            new_correct = label
    assert new_correct is not None  # guaranteed by the model validator
    return question.model_copy(update={"options": new_options, "correct_option_id": new_correct})


def target_to_questgen(question: TargetMCQuestion) -> dict[str, Any]:
    """Reverse adapter. Lossy: only chunk ids survive as ``source_ids``."""
    correct = next(opt for opt in question.options if opt.id == question.correct_option_id)
    return {
        "stem": question.question,
        "options": [opt.text for opt in question.options],
        "correct_answer": correct.text,
        "explanation": question.explanation,
        "source_ids": [ref.chunk_id for ref in question.source_refs if ref.chunk_id],
        "bloom_level": question.bloom_level.value,
        "difficulty": question.difficulty.value,
    }


# ==============================================================================
# Milestone M2 Inter-Module Hand-off Schemas (SV1 -> SV2 -> SV3)
# ==============================================================================

class ParsedPage(BaseModel):
    page: Optional[int] = Field(default=None, description="Page number for PDF (1-based), None for DOCX/TXT")
    text: str = Field(description="Extracted clean text content of the page or section")


class ParsedDocument(BaseModel):
    """Output of SV1 (Parsing & Validation) -> Input to SV2 (Chunking)"""
    file_name: str = Field(description="Name of the uploaded file")
    file_type: str = Field(description="File extension: 'pdf', 'docx', or 'txt'")
    sha256: str = Field(description="SHA-256 checksum to detect duplicates")
    pages: list[ParsedPage] = Field(description="List of extracted pages/sections")
    total_characters: int = Field(ge=1, description="Total non-whitespace characters extracted")


class DocumentChunk(BaseModel):
    """Output of SV2 (Chunking & Indexing) -> Input to Vector Store & SV3 (Retrieval)"""
    chunk_id: str = Field(description="Unique identifier for this chunk")
    doc_id: str = Field(description="Parent document identifier")
    course_id: str = Field(description="Course identifier for partition isolation")
    file_name: str = Field(description="Source file name")
    page: Optional[int] = Field(default=None, description="Page number if applicable")
    content: str = Field(min_length=10, description="Chunk text content")
    chunk_index: int = Field(ge=0, description="Ordinal index of the chunk in the document")


class RetrievedChunk(BaseModel):
    """A chunk returned by the vector store, with ranking info.

    Used as LLM context. Keeps ``chunk_id``/``chunk_index`` so callers can
    expand to neighbouring chunks, dedupe, filter by score, and record which
    chunk a question was generated from.
    """
    chunk_id: str
    doc_id: str
    course_id: str
    file_name: str
    page: Optional[int] = None
    chunk_index: int = Field(ge=0)
    content: str
    distance: Optional[float] = Field(
        default=None, description="Cosine distance from the query (0 = identical); None if not a similarity hit"
    )
    score: Optional[float] = Field(
        default=None, description="Cosine similarity = 1 - distance; None if not a similarity hit"
    )

    def to_source_reference(self, max_snippet_chars: int = 300) -> SourceReference:
        return SourceReference(
            doc_id=self.doc_id,
            file_name=self.file_name,
            page=self.page,
            snippet=make_snippet(self.content, max_snippet_chars),
            chunk_id=self.chunk_id,
        )


class RetrievalResult(BaseModel):
    """Output of SV3 (Course-Scoped Retrieval) -> Input to M3 (Question Generation)"""
    course_id: str = Field(description="Course scope of the retrieval")
    query: str = Field(description="Search prompt or query")
    matches: list[SourceReference] = Field(description="Relevant chunks formatted as SourceReferences")
    chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Full retrieved chunks (hits first, then optional neighbours), aligned with `matches`",
    )

    @classmethod
    def from_chunks(
        cls,
        *,
        course_id: str,
        query: str,
        chunks: list[RetrievedChunk],
        max_snippet_chars: int = 300,
    ) -> "RetrievalResult":
        return cls(
            course_id=course_id,
            query=query,
            chunks=list(chunks),
            matches=[chunk.to_source_reference(max_snippet_chars) for chunk in chunks],
        )


# ==============================================================================
# Learner model (adaptive quizzes)
# ==============================================================================

class Concept(BaseModel):
    concept_id: str
    course_id: str
    name: str = Field(min_length=1)


class QuizRequest(BaseModel):
    course_id: str
    learner_id: str
    num_questions: int = Field(ge=1, le=20)
    concept_ids: Optional[list[str]] = Field(
        default=None, description="None = let the system choose from the learner's weakest concepts"
    )
    target_difficulty: Optional[DifficultyLevel] = None


class AttemptRecord(BaseModel):
    learner_id: str
    question_id: str
    concept_ids: list[str] = Field(default_factory=list)
    selected_option_id: OptionId
    is_correct: bool
    difficulty: DifficultyLevel
    bloom_level: BloomLevel
    time_spent_seconds: Optional[float] = Field(default=None, ge=0)
    answered_at: datetime = Field(default_factory=_utcnow)


class ConceptMastery(BaseModel):
    learner_id: str
    concept_id: str
    mastery: float = Field(ge=0, le=1)
    attempts: int = Field(ge=0)
    updated_at: datetime = Field(default_factory=_utcnow)
