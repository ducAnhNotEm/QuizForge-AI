"""M3.P - Đóng gói ngữ cảnh (context) từ kết quả retrieval để đưa vào prompt.

Module này KHÔNG gọi LLM và không phụ thuộc framework nào (LangChain, Gemini SDK).
Đầu vào: danh sách ``RetrievedChunk`` (M2.C). Đầu ra: ``AssembledContext`` gồm
chuỗi context đã gắn thẻ nguồn và danh sách ``ContextSource`` để SV2/SV3 kiểm tra
``source_ids`` / ``evidence_quote`` sau khi model trả lời.

Quy trình:
    1. Làm sạch nội dung (NFC, bỏ ký tự điều khiển), bỏ chunk rỗng.
    2. Chọn chunk theo điểm retrieval cao nhất cho đến khi hết ngân sách token.
       Không cắt giữa chunk; chunk trùng hoặc nằm gọn trong chunk đã chọn bị bỏ.
    3. Sắp lại các chunk đã chọn theo thứ tự đọc (file -> doc -> chunk_index).
    4. Bỏ phần chồng lặp giữa hai chunk liên tiếp của cùng tài liệu.
    5. Bọc từng chunk trong thẻ ``<source>`` và toàn bộ trong ``<context>``;
       vô hiệu hóa mọi chuỗi giống thẻ của ta xuất hiện trong nội dung tài liệu
       (chống prompt injection bằng delimiter giả).
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from backend.schemas import RetrievedChunk

# --------------------------------------------------------------------------- #
# Hằng số
# --------------------------------------------------------------------------- #

DEFAULT_MAX_CONTEXT_TOKENS = 3000
DEFAULT_MAX_CHUNKS = 12

# Tiếng Việt tốn nhiều token hơn tiếng Anh; 3 ký tự/token là ước lượng thận trọng.
# SV2 có thể truyền ``token_counter`` thật (ví dụ count_tokens của Gemini).
CHARS_PER_TOKEN = 3

MIN_OVERLAP_CHARS = 30
MAX_OVERLAP_CHARS = 1000

CODE_CONTEXT_EMPTY = "CONTEXT_EMPTY"
CODE_CONTEXT_BUDGET = "CONTEXT_BUDGET_TOO_SMALL"
CODE_INVALID_ARGUMENT = "INVALID_ARGUMENT"

TokenCounter = Callable[[str], int]


# --------------------------------------------------------------------------- #
# Lỗi
# --------------------------------------------------------------------------- #


class PromptContextError(ValueError):
    """Lỗi của M3.P, có ``code`` ổn định để API ánh xạ.

    Kế thừa ``ValueError`` để code cũ bắt ``ValueError`` vẫn chạy. Khi M1.3 chốt
    bảng mã lỗi, chỉ cần đổi lớp cha / ánh xạ ``code`` tại đây.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Kiểu dữ liệu trả về (dataclass thuần Python)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ContextSource:
    """Một nguồn đã được đưa vào prompt. ``content`` là đúng phần chữ model nhìn thấy
    (sau khi bỏ chồng lặp), dùng để kiểm tra ``evidence_quote``."""

    source_id: str  # "S1", "S2", ... theo thứ tự đọc
    chunk_id: str
    doc_id: str
    file_name: str
    page: Optional[int]
    chunk_index: int
    location: str  # "Trang 42" hoặc "Đoạn 7" khi không có số trang
    content: str


@dataclass(frozen=True)
class AssembledContext:
    text: str
    sources: tuple[ContextSource, ...]
    token_estimate: int
    # chunk_id bị loại vì hết ngân sách token hoặc vượt max_chunks
    dropped_chunk_ids: tuple[str, ...]


# --------------------------------------------------------------------------- #
# Tiện ích văn bản
# --------------------------------------------------------------------------- #

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")
# Mọi thẻ mở/đóng <source ...> hoặc <context ...> (kể cả có khoảng trắng, hoa/thường).
_RESERVED_TAG = re.compile(r"<(\s*/?\s*(?:source|context)\b)", re.IGNORECASE)


def estimate_tokens(text: str) -> int:
    """Ước lượng token thận trọng cho tiếng Việt."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def normalize_for_match(text: str) -> str:
    """Chuẩn hóa NFC và gộp khoảng trắng, dùng khi so khớp ``evidence_quote``."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def neutralize_delimiters(text: str) -> str:
    """Biến ``<source`` / ``</context`` ... trong dữ liệu thành ``&lt;source`` ...
    để tài liệu không thể đóng thẻ sớm hoặc giả mạo một nguồn khác."""
    return _RESERVED_TAG.sub(r"&lt;\1", text)


def clean_single_line(text: str, max_len: int) -> str:
    """Làm sạch chuỗi do người dùng/hệ thống cung cấp để đặt vào một dòng của prompt."""
    text = normalize_for_match(_CONTROL_CHARS.sub("", text))
    return neutralize_delimiters(text)[:max_len].strip()


def _clean_content(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return _CONTROL_CHARS.sub("", text).strip()


def _score(chunk: RetrievedChunk) -> float:
    if chunk.score is not None:
        return float(chunk.score)
    if chunk.distance is not None:
        return 1.0 - float(chunk.distance)
    return float("-inf")


def _location_label(page: Optional[int], chunk_index: int) -> str:
    return f"Trang {page}" if page is not None else f"Đoạn {chunk_index}"


def _attr(value: str) -> str:
    return html.escape(" ".join(value.split()), quote=True)


def _render_block(source_id: str, file_name: str, location: str, content: str) -> str:
    return (
        f'<source id="{source_id}" file="{_attr(file_name)}" location="{_attr(location)}">\n'
        f"{neutralize_delimiters(content)}\n"
        f"</source>"
    )


def _strip_overlap(prev: str, cur: str) -> str:
    """Bỏ phần đầu của ``cur`` trùng với phần cuối của ``prev`` (overlap của chunker)."""
    max_k = min(len(prev), len(cur) - 1, MAX_OVERLAP_CHARS)
    for k in range(max_k, MIN_OVERLAP_CHARS - 1, -1):
        if prev.endswith(cur[:k]):
            return cur[k:].lstrip()
    return cur


def find_evidence(
    quote: str,
    sources: Sequence[ContextSource],
    source_ids: Optional[Sequence[str]] = None,
) -> bool:
    """True nếu ``quote`` xuất hiện trong (các) nguồn, sau khi chuẩn hóa NFC + khoảng trắng.

    Nếu ``source_ids`` được truyền, chỉ tìm trong các nguồn đó (id không tồn tại
    không khớp nguồn nào). Hàm tiện ích cho validator của M3.Q.
    """
    needle = normalize_for_match(quote or "")
    if not needle:
        return False
    allowed = set(source_ids) if source_ids is not None else None
    for src in sources:
        if allowed is not None and src.source_id not in allowed:
            continue
        if needle in normalize_for_match(src.content):
            return True
    return False


# --------------------------------------------------------------------------- #
# API chính
# --------------------------------------------------------------------------- #


def assemble_context(
    chunks: Sequence[RetrievedChunk],
    *,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    token_counter: TokenCounter = estimate_tokens,
) -> AssembledContext:
    """Đóng gói ``chunks`` thành context có thẻ nguồn. Xem docstring module."""
    if max_tokens <= 0 or max_chunks <= 0:
        raise PromptContextError(
            CODE_INVALID_ARGUMENT, "max_tokens and max_chunks must be positive"
        )

    # 1. Làm sạch, bỏ chunk rỗng.
    candidates: list[tuple[int, RetrievedChunk, str]] = []
    for pos, chunk in enumerate(chunks or []):
        content = _clean_content(chunk.content or "")
        if content:
            candidates.append((pos, chunk, content))
    if not candidates:
        raise PromptContextError(CODE_CONTEXT_EMPTY, "Context cannot be empty")

    # 2. Chọn theo điểm cao nhất; hòa điểm thì giữ thứ tự đầu vào (ổn định).
    ranked = sorted(candidates, key=lambda t: (-_score(t[1]), t[0]))
    selected: list[tuple[int, RetrievedChunk, str]] = []
    seen_ids: set[str] = set()
    seen_norms: list[str] = []
    dropped: list[str] = []
    used = 0

    for pos, chunk, content in ranked:
        norm = normalize_for_match(content)
        if chunk.chunk_id in seen_ids or any(norm in other for other in seen_norms):
            continue  # trùng lặp: bỏ im lặng, bản điểm cao hơn đã được chọn
        if len(selected) >= max_chunks:
            dropped.append(chunk.chunk_id)
            continue
        cost = token_counter(
            _render_block(
                "S00", chunk.file_name, _location_label(chunk.page, chunk.chunk_index), content
            )
        )
        if used + cost > max_tokens:
            dropped.append(chunk.chunk_id)  # không cắt giữa chunk; thử chunk nhỏ hơn
            continue
        selected.append((pos, chunk, content))
        seen_ids.add(chunk.chunk_id)
        seen_norms.append(norm)
        used += cost

    if not selected:
        raise PromptContextError(
            CODE_CONTEXT_BUDGET,
            f"No chunk fits within max_tokens={max_tokens}; increase the budget "
            "or re-chunk with smaller chunks",
        )

    # 3. Thứ tự đọc. chunk_index tăng theo trang nên không cần sắp theo page
    #    (page có thể None với DOCX/TXT).
    selected.sort(key=lambda t: (t[1].file_name, t[1].doc_id, t[1].chunk_index, t[0]))

    # 4 + 5. Bỏ chồng lặp, gán id nguồn, dựng khối.
    sources: list[ContextSource] = []
    blocks: list[str] = []
    prev_by_doc: dict[str, tuple[int, str]] = {}
    for _, chunk, original in selected:
        content = original
        prev = prev_by_doc.get(chunk.doc_id)
        if prev is not None and prev[0] + 1 == chunk.chunk_index:
            content = _strip_overlap(prev[1], original)
        prev_by_doc[chunk.doc_id] = (chunk.chunk_index, original)
        if not content:
            continue

        source_id = f"S{len(sources) + 1}"
        location = _location_label(chunk.page, chunk.chunk_index)
        sources.append(
            ContextSource(
                source_id=source_id,
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                file_name=chunk.file_name,
                page=chunk.page,
                chunk_index=chunk.chunk_index,
                location=location,
                content=content,
            )
        )
        blocks.append(_render_block(source_id, chunk.file_name, location, content))

    text = "<context>\n" + "\n\n".join(blocks) + "\n</context>"
    return AssembledContext(
        text=text,
        sources=tuple(sources),
        token_estimate=token_counter(text),
        dropped_chunk_ids=tuple(dropped),
    )
