"""Pure-Python helpers for turning raw LLM/QuestGen output into clean MCQ parts.

This module intentionally has no third-party dependencies so the parsing rules
can be unit-tested without Pydantic, Chroma, or a network.
"""

from __future__ import annotations

import random
import re
import unicodedata
from typing import Optional, Sequence

OPTION_LABELS: tuple[str, ...] = ("A", "B", "C", "D")

# "A. text", "a) text", "(B): text" ...
_OPTION_LABEL_PREFIX = re.compile(r"^\s*\(?([A-Da-d])[\.\)\:]\s+")
# The whole answer is just a letter: "B", "b", "(B)", "B.", "B)".
_LETTER_ONLY = re.compile(r"^\s*\(?([A-Da-d])\)?[\.\:]?\s*$")
# Letter followed by the option text: "B. Hà Nội".
_LETTER_WITH_TEXT = re.compile(r"^\s*\(?([A-Da-d])[\.\)\:]\s+(.+)$", re.DOTALL)

# Options that only make sense at a fixed position ("Cả A và B", "All of the
# above"). Shuffling such options would silently break the question.
_POSITIONAL_OPTION = re.compile(
    r"("
    r"tất cả (các )?(đáp án|phương án|lựa chọn|ý)"
    r"|(đáp án|phương án|lựa chọn) (trên|còn lại|[a-d]\b)"
    r"|không (có )?(đáp án|phương án) nào"
    r"|all of the above|none of the above|both [a-d]\b"
    r"|\b[a-d]\s*(và|and|&)\s*[a-d]\b"
    r")",
    re.IGNORECASE,
)


def canon_text(text: str) -> str:
    """Canonical form for comparing texts: NFC, collapsed spaces, casefolded."""
    normalized = unicodedata.normalize("NFC", str(text))
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def strip_option_labels(options: Sequence[str]) -> list[str]:
    """Remove "A. ", "B) " ... prefixes, but only when all options carry them
    in A, B, C, D order (so a legitimate "A. Nguyễn" option is left alone)."""
    cleaned = [str(option) for option in options]
    matches = [_OPTION_LABEL_PREFIX.match(option) for option in cleaned]
    if len(cleaned) == len(OPTION_LABELS) and all(matches):
        letters = [match.group(1).upper() for match in matches if match]
        if letters == list(OPTION_LABELS):
            return [option[match.end():].strip() for option, match in zip(cleaned, matches) if match]
    return [option.strip() for option in cleaned]


def resolve_correct_index(correct_answer: object, option_texts: Sequence[str]) -> Optional[int]:
    """Map a raw ``correct_answer`` to an option index (0-3), or ``None``.

    Accepted shapes: a single letter ("B", "(b)", "B."), letter + text
    ("B. Hà Nội"), or the full option text. A letter that contradicts the
    accompanying text raises ``ValueError`` instead of guessing.
    """
    answer = str(correct_answer or "").strip()
    if not answer:
        return None
    canon_options = [canon_text(text) for text in option_texts]

    letter_only = _LETTER_ONLY.match(answer)
    if letter_only:
        index = OPTION_LABELS.index(letter_only.group(1).upper())
        return index if index < len(canon_options) else None

    letter_idx: Optional[int] = None
    with_text = _LETTER_WITH_TEXT.match(answer)
    if with_text:
        letter_idx = OPTION_LABELS.index(with_text.group(1).upper())
        body = canon_text(with_text.group(2))
        if body in canon_options:
            text_idx = canon_options.index(body)
            if text_idx != letter_idx:
                raise ValueError(
                    f"correct_answer {answer!r} names option "
                    f"{OPTION_LABELS[letter_idx]} but its text matches option "
                    f"{OPTION_LABELS[text_idx]}"
                )
            return text_idx

    canon_answer = canon_text(answer)
    if canon_answer in canon_options:
        return canon_options.index(canon_answer)
    return letter_idx


def has_positional_option(option_texts: Sequence[str]) -> bool:
    """True if any option refers to other options or to its own position."""
    return any(_POSITIONAL_OPTION.search(text) for text in option_texts)


def shuffled_order(count: int, seed: int | str) -> list[int]:
    """Deterministic permutation of ``range(count)``.

    ``random.Random(str)`` is seeded from the string's bytes (not ``hash()``),
    so the same question id gives the same order across runs and processes.
    """
    order = list(range(count))
    random.Random(seed).shuffle(order)
    return order


def make_snippet(text: str, max_chars: int = 300) -> str:
    """Collapse whitespace and cut at a word boundary for citation display."""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= max_chars:
        return flat
    cut = flat[:max_chars].rsplit(" ", 1)[0] or flat[:max_chars]
    return cut.rstrip(",;:") + "…"
