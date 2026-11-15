"""Unit tests for SV2 document chunking and its metadata hand-off."""

from backend.ingestion import chunk_document
from backend.schemas import ParsedDocument, ParsedPage


def _lecture_text(prefix: str, paragraph_count: int = 18) -> str:
    paragraphs = [
        (
            f"{prefix}-{index:03d}: Sinh viên cần hiểu khái niệm, ghi nhớ nguyên tắc "
            f"và vận dụng kiến thức này vào bài tập số {index}."
        )
        for index in range(paragraph_count)
    ]
    return "\n\n".join(paragraphs)


def _parsed_document(*pages: ParsedPage, file_name: str = "lecture.pdf") -> ParsedDocument:
    total_characters = sum(
        1 for page in pages for character in page.text if not character.isspace()
    )
    return ParsedDocument(
        file_name=file_name,
        file_type=file_name.rsplit(".", 1)[-1],
        sha256="a" * 64,
        pages=list(pages),
        total_characters=total_characters,
    )


def _longest_suffix_prefix_overlap(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    for length in range(limit, 0, -1):
        if left.endswith(right[:length]):
            return length
    return 0


def test_chunks_respect_size_limit_and_keep_overlap() -> None:
    text = _lecture_text("CHUNK", paragraph_count=30)
    document = _parsed_document(ParsedPage(page=1, text=text))

    chunks = chunk_document(
        document,
        doc_id="doc-length",
        course_id="course-algorithms",
        chunk_size_chars=190,
        overlap_chars=30,
    )

    assert len(chunks) > 1
    assert all(10 <= len(chunk.content) <= 190 for chunk in chunks)
    assert all(
        _longest_suffix_prefix_overlap(left.content, right.content) >= 18
        for left, right in zip(chunks, chunks[1:])
    )

    for index in range(30):
        assert f"CHUNK-{index:03d}" in "\n".join(chunk.content for chunk in chunks)


def test_chunk_metadata_stays_with_its_page_and_document() -> None:
    document = _parsed_document(
        ParsedPage(page=1, text=_lecture_text("PAGE-ONE", paragraph_count=18)),
        ParsedPage(page=2, text=_lecture_text("PAGE-TWO", paragraph_count=18)),
    )

    chunks = chunk_document(
        document,
        doc_id="doc-pages",
        course_id="course-algorithms",
        chunk_size_chars=190,
        overlap_chars=30,
    )

    assert chunks
    assert {chunk.page for chunk in chunks} == {1, 2}
    assert all(chunk.doc_id == "doc-pages" for chunk in chunks)
    assert all(chunk.course_id == "course-algorithms" for chunk in chunks)
    assert all(chunk.file_name == "lecture.pdf" for chunk in chunks)

    page_one_chunks = [chunk for chunk in chunks if chunk.page == 1]
    page_two_chunks = [chunk for chunk in chunks if chunk.page == 2]
    assert page_one_chunks and page_two_chunks
    assert all("PAGE-TWO" not in chunk.content for chunk in page_one_chunks)
    assert all("PAGE-ONE" not in chunk.content for chunk in page_two_chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunks_preserve_missing_page_and_have_stable_unique_ids() -> None:
    document = _parsed_document(
        ParsedPage(page=None, text=_lecture_text("TEXT-DOC", paragraph_count=20)),
        file_name="lecture.txt",
    )

    first_pass = chunk_document(
        document,
        doc_id="doc-text",
        course_id="course-literature",
        chunk_size_chars=190,
        overlap_chars=30,
    )
    second_pass = chunk_document(
        document,
        doc_id="doc-text",
        course_id="course-literature",
        chunk_size_chars=190,
        overlap_chars=30,
    )

    assert first_pass
    assert all(chunk.page is None for chunk in first_pass)
    assert len({chunk.chunk_id for chunk in first_pass}) == len(first_pass)
    assert [chunk.chunk_id for chunk in first_pass] == [
        chunk.chunk_id for chunk in second_pass
    ]
    assert [chunk.chunk_index for chunk in first_pass] == list(range(len(first_pass)))
