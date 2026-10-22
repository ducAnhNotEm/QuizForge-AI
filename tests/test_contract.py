"""
Contract and Schema Tests for QuizForge-AI.
Milestone: M1 (API Contract & Schema Mapping)

Verifies:
1. Target MCQ Schema validation rules (exactly 4 options, valid correct option ID, non-empty fields).
2. Bi-directional Adapter from QuestGen GeneratedQuestion format to QuizForge Target Schema.
3. Edge case error handling (invalid options count, correct answer mismatch, empty stem).
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.schemas import (
    TargetMCQuestion,
    OptionItem,
    SourceReference,
    QuestionStatus,
    questgen_to_target_schema
)


@pytest.fixture
def mock_contract_data():
    fixture_path = Path(__file__).parent / "fixtures" / "mock_contract_data.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_target_schema_valid_creation():
    """Verify that a compliant MCQ passes validation cleanly."""
    mcq = TargetMCQuestion(
        id="q_100",
        course_id="course_cs101",
        type="mcq",
        question="Độ phức tạp thuật toán tìm kiếm nhị phân là gì?",
        options=[
            OptionItem(id="A", text="O(1)"),
            OptionItem(id="B", text="O(log n)"),
            OptionItem(id="C", text="O(n)"),
            OptionItem(id="D", text="O(n^2)")
        ],
        correct_option_id="B",
        explanation="Thuật toán chia đôi tập dữ liệu sau mỗi bước so sánh.",
        source_refs=[
            SourceReference(
                doc_id="doc_01",
                file_name="algorithms.pdf",
                page=12,
                snippet="Binary search runs in O(log n) time."
            )
        ],
        status=QuestionStatus.DRAFT
    )
    assert mcq.id == "q_100"
    assert mcq.correct_option_id == "B"
    assert len(mcq.options) == 4
    assert mcq.status == QuestionStatus.DRAFT


def test_target_schema_rejects_non_4_options():
    """Schema must reject question with less than or greater than 4 options."""
    with pytest.raises(ValidationError):
        TargetMCQuestion(
            id="q_bad_opts",
            course_id="course_cs101",
            question="Câu hỏi có ít hơn 4 lựa chọn?",
            options=[
                OptionItem(id="A", text="Lựa chọn 1"),
                OptionItem(id="B", text="Lựa chọn 2"),
                OptionItem(id="C", text="Lựa chọn 3")
            ],
            correct_option_id="A",
            explanation="Giải thích mẫu."
        )


def test_target_schema_rejects_mismatched_correct_option():
    """Schema must reject if correct_option_id is not in options list."""
    with pytest.raises(ValidationError) as exc_info:
        TargetMCQuestion(
            id="q_mismatch",
            course_id="course_cs101",
            question="Đáp án đúng có ID lạ không có trong danh sách?",
            options=[
                OptionItem(id="A", text="Opt A"),
                OptionItem(id="B", text="Opt B"),
                OptionItem(id="C", text="Opt C"),
                OptionItem(id="D", text="Opt D")
            ],
            correct_option_id="Z",  # Not in A, B, C, D
            explanation="Giải thích mẫu."
        )
    assert "does not match any option ID" in str(exc_info.value)


def test_target_schema_rejects_duplicate_options():
    """Schema must reject duplicate option texts."""
    with pytest.raises(ValidationError) as exc_info:
        TargetMCQuestion(
            id="q_duplicate",
            course_id="course_cs101",
            question="Câu hỏi có hai phương án nội dung y hệt nhau?",
            options=[
                OptionItem(id="A", text="Đáp án A"),
                OptionItem(id="B", text="Đáp án A"),  # Duplicate
                OptionItem(id="C", text="Đáp án C"),
                OptionItem(id="D", text="Đáp án D")
            ],
            correct_option_id="A",
            explanation="Giải thích mẫu."
        )
    assert "All 4 option texts must be unique" in str(exc_info.value)


def test_questgen_adapter_successful_mapping(mock_contract_data):
    """
    Test adapter converting QuestGen GeneratedQuestion format
    into TargetMCQuestion compliant schema.
    """
    raw_questgen = mock_contract_data["questgen_sample"]
    source_lookup = mock_contract_data["questgen_sources_table"]

    target_mcq = questgen_to_target_schema(
        questgen_data=raw_questgen,
        question_id="q_test_001",
        course_id="course_cntt",
        source_lookup=source_lookup,
        status="pending"
    )

    assert target_mcq.id == "q_test_001"
    assert target_mcq.course_id == "course_cntt"
    assert target_mcq.question == raw_questgen["stem"]
    assert len(target_mcq.options) == 4
    # In raw_questgen, the correct_answer is "Mảng đã được sắp xếp thứ tự", which is the first option (A)
    assert target_mcq.correct_option_id == "A"
    assert target_mcq.status == QuestionStatus.DRAFT
    assert len(target_mcq.source_refs) == 1
    assert target_mcq.source_refs[0].file_name == "Giao_trinh_CTDL_GT.pdf"
    assert target_mcq.source_refs[0].page == 25


def test_questgen_adapter_error_when_correct_answer_not_in_options(mock_contract_data):
    """Adapter must raise an exception when QuestGen's correct_answer doesn't match any option."""
    bad_data = {
        "stem": "Câu hỏi test lỗi",
        "options": ["A1", "A2", "A3", "A4"],
        "correct_answer": "Hoàn toàn khác",
        "explanation": "Giải thích",
        "source_ids": []
    }
    with pytest.raises(ValueError) as exc:
        questgen_to_target_schema(
            questgen_data=bad_data,
            question_id="q_err",
            course_id="c_01"
        )
    assert "not found in options" in str(exc.value)
