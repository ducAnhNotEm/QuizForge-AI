import pytest
from pydantic import ValidationError

from backend.schemas import (
    BloomLevel,
    DifficultyLevel,
    OptionItem,
    QuestionStatus,
    RetrievalResult,
    RetrievedChunk,
    TargetMCQuestion,
    questgen_to_target_schema,
    shuffle_options,
    target_to_questgen,
)

SOURCES = {"s1": {"doc_id": "d1", "file_name": "a.pdf", "page": 3, "snippet": "Trích đoạn", "chunk_id": "c1"}}


def qg(**overrides):
    data = {
        "stem": "Thủ đô của Việt Nam là thành phố nào?",
        "options": ["Hà Nội", "Huế", "Đà Nẵng", "Cần Thơ"],
        "correct_answer": "Hà Nội",
        "explanation": "Hà Nội là thủ đô của Việt Nam.",
        "source_ids": ["s1"],
    }
    data.update(overrides)
    return data


def convert(data=None, **kwargs):
    return questgen_to_target_schema(data or qg(), "q1", "course1", SOURCES, **kwargs)


def correct_text(q):
    return next(o.text for o in q.options if o.id == q.correct_option_id)


def test_option_ids_are_normalized_not_just_checked():
    assert OptionItem(id=" b ", text="x").id == "B"
    with pytest.raises(ValidationError):
        OptionItem(id="E", text="x")


def test_correct_option_id_is_normalized():
    q = TargetMCQuestion(
        id="q", course_id="c", question="Câu hỏi đủ dài?",
        options=[OptionItem(id=i, text=t) for i, t in zip("ABCD", ["1", "2", "3", "4"])],
        correct_option_id=" c ", explanation="Giải thích đủ dài.",
    )
    assert q.correct_option_id == "C"


@pytest.mark.parametrize("answer", ["Hà Nội", "A", "a", "A. Hà Nội", "(a)"])
def test_adapter_accepts_many_answer_formats(answer):
    q = convert(qg(correct_answer=answer), shuffle=False)
    assert q.correct_option_id == "A"


def test_adapter_strips_labelled_options():
    q = convert(qg(options=["A. Hà Nội", "B. Huế", "C. Đà Nẵng", "D. Cần Thơ"], correct_answer="B"), shuffle=False)
    assert [o.text for o in q.options][0] == "Hà Nội" and q.correct_option_id == "B"


def test_unknown_source_id_raises_by_default_and_warns_when_lenient():
    with pytest.raises(ValueError, match="s9"):
        convert(qg(source_ids=["s1", "s9"]))
    q = convert(qg(source_ids=["s1", "s9"]), strict_sources=False)
    assert len(q.source_refs) == 1 and q.source_refs[0].chunk_id == "c1"


def test_accepted_requires_a_source():
    with pytest.raises(ValidationError):
        questgen_to_target_schema(qg(source_ids=[]), "q", "c", SOURCES, status="approved")
    ok = convert(status="approved")
    assert ok.status is QuestionStatus.ACCEPTED


def test_assignment_cannot_bypass_source_rule():
    q = convert(qg(source_ids=[]))
    with pytest.raises(ValidationError):
        q.status = QuestionStatus.ACCEPTED


def test_bad_labels_warn_and_fall_back_or_raise_in_strict_mode(caplog):
    q = convert(qg(bloom_level="nonsense", difficulty="???"))
    assert q.bloom_level is BloomLevel.UNDERSTAND and q.difficulty is DifficultyLevel.MEDIUM
    assert "Unknown bloom_level" in caplog.text
    with pytest.raises(ValueError):
        convert(qg(bloom_level="nonsense"), strict_labels=True)


def test_vietnamese_label_aliases():
    q = convert(qg(bloom_level="Vận dụng", difficulty="Khó"))
    assert q.bloom_level is BloomLevel.APPLY and q.difficulty is DifficultyLevel.HARD


def test_non_string_labels_do_not_crash():
    q = convert(qg(bloom_level=BloomLevel.CREATE, difficulty=DifficultyLevel.EASY))
    assert q.bloom_level is BloomLevel.CREATE and q.difficulty is DifficultyLevel.EASY


def test_shuffle_keeps_the_correct_answer_and_is_deterministic():
    unshuffled = convert(shuffle=False)
    a, b = shuffle_options(unshuffled), shuffle_options(unshuffled)
    assert a == b
    assert correct_text(a) == "Hà Nội"
    assert [o.id for o in a.options] == ["A", "B", "C", "D"]


def test_answers_do_not_always_land_on_the_same_letter():
    letters = set()
    for i in range(30):
        q = questgen_to_target_schema(qg(), f"q{i}", "c", SOURCES)
        letters.add(q.correct_option_id)
        assert correct_text(q) == "Hà Nội"
    assert len(letters) > 1


def test_positional_options_are_not_shuffled():
    data = qg(options=["Hà Nội", "Huế", "Đà Nẵng", "Cả A và B đều đúng"], correct_answer="Cả A và B đều đúng")
    q = convert(data)
    assert [o.text for o in q.options][3] == "Cả A và B đều đúng" and q.correct_option_id == "D"


def test_duplicate_options_rejected():
    with pytest.raises(ValidationError):
        convert(qg(options=["Hà Nội", "hà nội ", "Đà Nẵng", "Cần Thơ"]))


def test_reverse_adapter_round_trip():
    q = convert(shuffle=False)
    back = target_to_questgen(q)
    q2 = questgen_to_target_schema(back, "q1", "course1", {"c1": SOURCES["s1"]}, shuffle=False)
    assert correct_text(q2) == correct_text(q) and [o.text for o in q2.options] == [o.text for o in q.options]


def test_retrieved_chunk_to_source_reference_and_result():
    chunk = RetrievedChunk(chunk_id="c9", doc_id="d", course_id="c", file_name="f.pdf", page=None,
                           chunk_index=4, content="nội dung " * 100, distance=0.2, score=0.8)
    ref = chunk.to_source_reference(60)
    assert ref.chunk_id == "c9" and ref.page is None and len(ref.snippet) <= 61
    result = RetrievalResult.from_chunks(course_id="c", query="q", chunks=[chunk])
    assert len(result.matches) == len(result.chunks) == 1
