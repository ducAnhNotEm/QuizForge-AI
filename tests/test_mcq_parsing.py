import pytest

from backend.mcq_parsing import (
    canon_text,
    has_positional_option,
    make_snippet,
    resolve_correct_index,
    shuffled_order,
    strip_option_labels,
)

OPTIONS = ["Hà Nội", "Huế", "Đà Nẵng", "Cần Thơ"]


@pytest.mark.parametrize("answer,expected", [
    ("B", 1), ("b", 1), ("(c)", 2), ("D.", 3), ("A)", 0),
    ("Hà Nội", 0), ("  huế ", 1), ("B. Huế", 1), ("c) Đà Nẵng", 2),
])
def test_resolve_correct_index_accepts_letters_and_text(answer, expected):
    assert resolve_correct_index(answer, OPTIONS) == expected


def test_resolve_correct_index_unknown_returns_none():
    assert resolve_correct_index("Hải Phòng", OPTIONS) is None
    assert resolve_correct_index("", OPTIONS) is None


def test_resolve_correct_index_conflicting_letter_and_text_raises():
    with pytest.raises(ValueError):
        resolve_correct_index("A. Huế", OPTIONS)


def test_resolve_correct_index_letter_with_unmatched_text_uses_letter():
    assert resolve_correct_index("B. nội dung hơi khác", OPTIONS) == 1


def test_resolve_handles_nfd_vs_nfc():
    import unicodedata
    nfd = unicodedata.normalize("NFD", "Hà Nội")
    assert resolve_correct_index(nfd, OPTIONS) == 0


def test_strip_option_labels_only_when_all_labelled_in_order():
    assert strip_option_labels(["A. x1", "B. x2", "C. x3", "D. x4"]) == ["x1", "x2", "x3", "x4"]
    assert strip_option_labels(["a) x1", "b) x2", "c) x3", "d) x4"]) == ["x1", "x2", "x3", "x4"]
    # Not all labelled / wrong order: leave untouched (a real "A. Nguyễn" must survive).
    mixed = ["A. Nguyễn", "Trần", "Lê", "Phạm"]
    assert strip_option_labels(mixed) == mixed
    assert strip_option_labels(["B. x", "A. y", "C. z", "D. w"]) == ["B. x", "A. y", "C. z", "D. w"]


@pytest.mark.parametrize("texts,expected", [
    (["Cả A và B đều đúng", "x", "y", "z"], True),
    (["Tất cả các đáp án trên", "x", "y", "z"], True),
    (["Không có đáp án nào đúng", "x", "y", "z"], True),
    (["All of the above", "x", "y", "z"], True),
    (["Both A and B", "x", "y", "z"], True),
    (["Hà Nội", "Huế", "Đà Nẵng", "Cần Thơ"], False),
    (["Tất cả sinh viên đều đỗ", "x", "y", "z"], False),
])
def test_has_positional_option(texts, expected):
    assert has_positional_option(texts) is expected


def test_shuffled_order_is_deterministic_permutation():
    a = shuffled_order(4, "q-123")
    assert a == shuffled_order(4, "q-123")
    assert sorted(a) == [0, 1, 2, 3]
    # Different ids should not all produce the identity permutation.
    assert any(shuffled_order(4, f"q-{i}") != [0, 1, 2, 3] for i in range(20))


def test_shuffle_does_not_always_keep_answer_in_place():
    positions = {shuffled_order(4, f"q-{i}").index(1) for i in range(40)}
    assert len(positions) > 1


def test_make_snippet_truncates_on_word_boundary():
    text = "một hai ba " * 100
    snippet = make_snippet(text, 50)
    assert snippet.endswith("…") and len(snippet) <= 51
    assert make_snippet("  ngắn   gọn \n", 50) == "ngắn gọn"


def test_canon_text_collapses_whitespace_and_case():
    assert canon_text("  Hà   NỘI ") == canon_text("hà nội")
