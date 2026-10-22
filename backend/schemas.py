"""
Pydantic Schemas and Contract Adapters for QuizForge-AI.
Milestone: M1 (API Contract & Schema Mapping)

This module defines:
1. Target Question Schema: Standard MCQ schema used by QuizForge-AI.
2. Adapter functions: Bi-directional transformation between QuestGen-AI-Agent format
   and QuizForge-AI target format.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class QuestionStatus(str, Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class OptionItem(BaseModel):
    id: str = Field(description="Option identifier, e.g., 'A', 'B', 'C', 'D'")
    text: str = Field(min_length=1, description="Option display text")


class SourceReference(BaseModel):
    doc_id: str = Field(description="Associated document ID")
    file_name: str = Field(description="Original file name")
    page: Optional[int] = Field(default=None, description="Page number if available, otherwise null")
    snippet: str = Field(description="Relevant extracted text segment")


class TargetMCQuestion(BaseModel):
    id: str = Field(description="Unique question identifier")
    course_id: str = Field(description="Target course ID")
    type: str = Field(default="mcq", description="Question type, defaults to 'mcq'")
    question: str = Field(min_length=5, description="The main question prompt (stem)")
    options: list[OptionItem] = Field(
        min_length=4,
        max_length=4,
        description="Exactly 4 unique options (A, B, C, D)"
    )
    correct_option_id: str = Field(
        description="ID of the correct option (must be one of 'A', 'B', 'C', 'D')"
    )
    explanation: str = Field(min_length=5, description="Clear rationale explaining the correct answer")
    source_refs: list[SourceReference] = Field(
        default_factory=list,
        description="Evidence excerpts supporting the question"
    )
    status: QuestionStatus = Field(
        default=QuestionStatus.DRAFT,
        description="Review status of the question"
    )

    @model_validator(mode="after")
    def validate_mcq_integrity(self):
        # 1. Ensure exactly 4 options with unique option IDs
        option_ids = [opt.id.strip().upper() for opt in self.options]
        if len(set(option_ids)) != 4:
            raise ValueError("MCQ must have exactly 4 unique option IDs (e.g. A, B, C, D)")

        # 2. Ensure option texts are unique (no duplicates)
        option_texts = [opt.text.strip().casefold() for opt in self.options]
        if len(set(option_texts)) != 4:
            raise ValueError("All 4 option texts must be unique")

        # 3. Ensure correct_option_id matches one of the option IDs
        target_correct = self.correct_option_id.strip().upper()
        if target_correct not in option_ids:
            raise ValueError(
                f"correct_option_id '{self.correct_option_id}' does not match any option ID {option_ids}"
            )
        return self


# ==============================================================================
# Adapter Functions: QuestGen <--> Target Schema
# ==============================================================================

def questgen_to_target_schema(
    questgen_data: dict[str, Any],
    question_id: str,
    course_id: str,
    source_lookup: Optional[dict[str, dict]] = None,
    status: str = "draft"
) -> TargetMCQuestion:
    """
    Transforms QuestGen's GeneratedQuestion format into QuizForge's TargetMCQuestion.

    QuestGen format:
    {
        "stem": "...",
        "options": ["text1", "text2", "text3", "text4"],
        "correct_answer": "text1",
        "explanation": "...",
        "source_ids": ["src_1"]
    }
    """
    stem = questgen_data.get("stem") or questgen_data.get("question") or ""
    raw_options = questgen_data.get("options") or []
    correct_answer = questgen_data.get("correct_answer") or ""
    explanation = questgen_data.get("explanation") or ""
    source_ids = questgen_data.get("source_ids") or []

    if len(raw_options) != 4:
        raise ValueError(f"QuestGen data must have exactly 4 options, got {len(raw_options)}")

    labels = ["A", "B", "C", "D"]
    formatted_options = [
        OptionItem(id=labels[i], text=str(raw_options[i]).strip())
        for i in range(4)
    ]

    # Find which label corresponds to correct_answer
    correct_option_id = None
    for item in formatted_options:
        if item.text.strip().casefold() == correct_answer.strip().casefold():
            correct_option_id = item.id
            break

    if not correct_option_id:
        raise ValueError(
            f"correct_answer '{correct_answer}' not found in options: {raw_options}"
        )

    # Build source references
    source_refs: list[SourceReference] = []
    if source_lookup:
        for sid in source_ids:
            if sid in source_lookup:
                info = source_lookup[sid]
                source_refs.append(
                    SourceReference(
                        doc_id=info.get("doc_id", "doc_unknown"),
                        file_name=info.get("file_name", "Unknown File"),
                        page=info.get("page"),
                        snippet=info.get("snippet", "")
                    )
                )

    # Map status
    status_map = {
        "pending": QuestionStatus.DRAFT,
        "draft": QuestionStatus.DRAFT,
        "approved": QuestionStatus.ACCEPTED,
        "accepted": QuestionStatus.ACCEPTED,
        "rejected": QuestionStatus.REJECTED
    }
    mapped_status = status_map.get(status.lower(), QuestionStatus.DRAFT)

    return TargetMCQuestion(
        id=question_id,
        course_id=course_id,
        type="mcq",
        question=stem,
        options=formatted_options,
        correct_option_id=correct_option_id,
        explanation=explanation,
        source_refs=source_refs,
        status=mapped_status
    )
