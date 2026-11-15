"""Document chunking for the QuizForge-AI ingestion pipeline.

The chunker works on the parsed pages produced by ``backend.documents``. It
keeps page boundaries intact so every chunk can be cited with the page number
already present in the hand-off schema.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, Sequence

from backend.schemas import DocumentChunk, ParsedDocument


# Initial settings mirror the upstream QuestGen character-window defaults.
# They are configurable because the best size depends on the embedding model
# and on the course materials being indexed.
DEFAULT_CHUNK_SIZE_CHARS = 1_100
DEFAULT_CHUNK_OVERLAP_CHARS = 140
MIN_CHUNK_CHARS = 10

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")
_SENTENCE_END = re.compile(r"([.!?][\"'’”\)\]]*)[ \t\n]+")
_LINE_BREAK = re.compile(r"\n+")
_WHITESPACE = re.compile(r"\s+")


class DocumentEmbedder(Protocol):
    model_name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


class ChunkVectorStore(Protocol):
    embedding_model: str

    def upsert_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> int: ...


def _cut_at_boundary(
    text: str,
    start: int,
    max_end: int,
    min_end: int,
) -> int | None:
    """Return a preferred cut position within the current character window.

    Paragraph boundaries take priority, followed by sentence endings, single
    line breaks, and spaces. Searching begins halfway through the window to
    avoid producing very small chunks just to hit an early boundary.
    """
    patterns: tuple[tuple[int, re.Pattern[str]], ...] = (
        (4, _PARAGRAPH_BREAK),
        (3, _SENTENCE_END),
        (2, _LINE_BREAK),
        (1, _WHITESPACE),
    )

    for _priority, pattern in patterns:
        candidates: list[int] = []
        for match in pattern.finditer(text, min_end, max_end + 1):
            if pattern is _SENTENCE_END:
                # Keep terminal punctuation (and a closing quote) in the
                # preceding chunk; whitespace belongs to the next window.
                position = match.start(1) + len(match.group(1))
            else:
                position = match.start()
            if start < position <= max_end:
                candidates.append(position)
        if candidates:
            return max(candidates)
    return None


def _overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    """Choose the next start near the requested overlap, preferring boundaries."""
    target = max(start + 1, end - overlap)
    if target >= end:
        return target

    # If a sentence boundary is close to the target, begin the next chunk at
    # the next sentence. This keeps the overlap readable instead of starting
    # in the middle of a word or sentence.
    search_radius = min(50, max(8, overlap // 4))
    lower = max(start + 1, target - search_radius)
    upper = min(end - 1, target + search_radius)
    sentence_starts = [
        match.end()
        for match in _SENTENCE_END.finditer(text, lower, end)
        if lower <= match.end() <= upper
    ]
    if sentence_starts:
        return min(sentence_starts, key=lambda position: abs(position - target))

    # Otherwise align to a nearby whitespace so a word is not split across
    # the overlap boundary. Fall back to the exact character offset if needed.
    whitespace_starts = [
        match.end()
        for match in _WHITESPACE.finditer(text, lower, min(end, upper + 1))
        if lower <= match.end() <= upper
    ]
    if whitespace_starts:
        return min(whitespace_starts, key=lambda position: abs(position - target))
    return target


def _split_page(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split one page into bounded chunks while retaining an overlap."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    if len(normalized) < MIN_CHUNK_CHARS:
        raise ValueError(
            "A non-empty parsed page must contain at least "
            f"{MIN_CHUNK_CHARS} characters to form a DocumentChunk."
        )

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        max_end = min(len(normalized), start + chunk_size)
        if max_end == len(normalized):
            end = max_end
        else:
            min_end = start + max(1, chunk_size // 2)
            end = _cut_at_boundary(normalized, start, max_end, min_end) or max_end

            # Avoid leaving a final tail too short for DocumentChunk.content.
            # Pull the cut back slightly; overlap will still carry the tail's
            # context into the following chunk without exceeding chunk_size.
            remaining = len(normalized) - end
            if 0 < remaining < MIN_CHUNK_CHARS:
                end = len(normalized) - MIN_CHUNK_CHARS

        content = normalized[start:end].strip()
        if len(content) >= MIN_CHUNK_CHARS:
            chunks.append(content)

        if end >= len(normalized):
            break

        next_start = _overlap_start(normalized, start, end, overlap)
        if next_start <= start:
            # Defensive progress guarantee for unusual punctuation/whitespace.
            next_start = min(end, start + 1)
        start = next_start

    return chunks


def chunk_document(
    document: ParsedDocument,
    *,
    doc_id: str,
    course_id: str,
    chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[DocumentChunk]:
    """Convert a parsed document into page-aware ``DocumentChunk`` objects.

    Chunks are ordered across the whole document. Pages are split separately,
    so a chunk's ``page`` always refers to all of its content. DOCX/TXT parser
    output may use ``page=None``; that value is preserved.
    """
    if not doc_id.strip():
        raise ValueError("doc_id must not be empty")
    if not course_id.strip():
        raise ValueError("course_id must not be empty")
    if chunk_size_chars < MIN_CHUNK_CHARS:
        raise ValueError(f"chunk_size_chars must be at least {MIN_CHUNK_CHARS}")
    if overlap_chars < 0 or overlap_chars >= chunk_size_chars:
        raise ValueError("overlap_chars must be between 0 and chunk_size_chars - 1")

    result: list[DocumentChunk] = []
    for parsed_page in document.pages:
        page_chunks = _split_page(
            parsed_page.text,
            chunk_size=chunk_size_chars,
            overlap=overlap_chars,
        )
        for content in page_chunks:
            chunk_index = len(result)
            chunk_id = hashlib.sha256(
                f"{doc_id}:{chunk_index}".encode("utf-8")
            ).hexdigest()[:32]
            result.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    course_id=course_id,
                    file_name=document.file_name,
                    page=parsed_page.page,
                    content=content,
                    chunk_index=chunk_index,
                )
            )

    return result


def index_document(
    document: ParsedDocument,
    *,
    doc_id: str,
    course_id: str,
    embedder: DocumentEmbedder | None = None,
    vector_store: ChunkVectorStore | None = None,
    chunk_size_chars: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[DocumentChunk]:
    """Chunk, embed, then persist one parsed document.

    Provider and store dependencies are injectable for callers that need a
    different embedding service or a test double. Defaults use the configured
    Ollama provider and local persistent ChromaDB collection.
    """
    chunks = chunk_document(
        document,
        doc_id=doc_id,
        course_id=course_id,
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
    )
    if not chunks:
        return []

    if embedder is None:
        from backend.embeddings import create_embedding_provider

        embedder = create_embedding_provider()

    embeddings = embedder.embed_documents([chunk.content for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise ValueError(
            f"Embedding provider returned {len(embeddings)} vectors for "
            f"{len(chunks)} chunks."
        )

    if vector_store is None:
        from backend.vector_store import ChromaVectorStore

        vector_store = ChromaVectorStore(embedding_model=embedder.model_name)
    elif vector_store.embedding_model != embedder.model_name:
        raise ValueError(
            "The vector store and embedding provider must use the same model."
        )

    vector_store.upsert_chunks(chunks, embeddings)
    return chunks
