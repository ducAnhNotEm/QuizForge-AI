"""Persistent ChromaDB storage for page-aware document chunks."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Sequence

from backend.schemas import DocumentChunk


DEFAULT_COLLECTION_NAME = "quizforge_chunks_v1"
MAX_UPSERT_BATCH_SIZE = 128


def _validated_embeddings(
    embeddings: Sequence[Sequence[float]], expected_count: int
) -> list[list[float]]:
    if len(embeddings) != expected_count:
        raise ValueError(
            f"Received {len(embeddings)} embeddings for {expected_count} chunks."
        )

    result: list[list[float]] = []
    dimensions: int | None = None
    for embedding in embeddings:
        if not embedding:
            raise ValueError("Embedding vectors must not be empty.")
        vector: list[float] = []
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Embedding vectors must contain only numeric values.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise ValueError("Embedding vectors cannot contain NaN or infinity.")
            vector.append(numeric_value)

        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise ValueError("All embeddings in a document must have the same dimension.")
        result.append(vector)
    return result


class ChromaVectorStore:
    """Chroma adapter that stores chunks and enforces embedding-model identity."""

    def __init__(
        self,
        *,
        embedding_model: str,
        path: str | Path | None = None,
        collection_name: str | None = None,
        client: object | None = None,
    ) -> None:
        if not embedding_model.strip():
            raise ValueError("embedding_model must not be empty.")

        if client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise RuntimeError(
                    "ChromaDB is not installed. Install backend requirements first."
                ) from exc

            default_path = Path(__file__).resolve().parent / "data" / "chroma"
            configured_path = path or os.getenv("QUIZFORGE_CHROMA_PATH", str(default_path))
            storage_path = Path(configured_path).expanduser().resolve()
            storage_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(storage_path))

        self.embedding_model = embedding_model
        self.collection_name = (
            collection_name
            or os.getenv("QUIZFORGE_CHROMA_COLLECTION", DEFAULT_COLLECTION_NAME)
        )
        self.client = client
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model,
                "schema_version": 1,
            },
            # Embeddings are produced by the configured provider and passed
            # explicitly; Chroma must not silently choose another model.
            embedding_function=None,
        )

        collection_metadata = self.collection.metadata or {}
        stored_model = collection_metadata.get("embedding_model")
        if stored_model != embedding_model:
            raise ValueError(
                f"Collection '{self.collection_name}' uses embedding model "
                f"{stored_model!r}; configured model is {embedding_model!r}. "
                "Use a new collection and re-index documents when changing models."
            )
        if collection_metadata.get("hnsw:space") != "cosine":
            raise ValueError(
                f"Collection '{self.collection_name}' must use cosine distance. "
                "Use a new collection and re-index documents to change the metric."
            )

    @staticmethod
    def _document_scope(course_id: str, doc_id: str) -> dict:
        return {
            "$and": [
                {"course_id": course_id},
                {"doc_id": doc_id},
            ]
        }

    def upsert_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """Insert or update one document's chunks, then remove stale old chunks."""
        if not chunks:
            if embeddings:
                raise ValueError("Cannot store embeddings without document chunks.")
            return 0

        doc_ids = {chunk.doc_id for chunk in chunks}
        course_ids = {chunk.course_id for chunk in chunks}
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(doc_ids) != 1 or len(course_ids) != 1:
            raise ValueError("A single upsert must contain chunks from one document and course.")
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("Chunk IDs must be unique within an upsert.")

        vectors = _validated_embeddings(embeddings, expected_count=len(chunks))
        doc_id = next(iter(doc_ids))
        course_id = next(iter(course_ids))
        scope = self._document_scope(course_id, doc_id)

        # Read prior IDs before writing. If a document was re-chunked into
        # fewer pieces, the old trailing chunks can be deleted after upsert.
        previous = self.collection.get(where=scope, include=["metadatas"])
        previous_ids = set(previous.get("ids", []))

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str | int]] = []
        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)
            metadata: dict[str, str | int] = {
                "course_id": chunk.course_id,
                "doc_id": chunk.doc_id,
                "chunk_id": chunk.chunk_id,
                "file_name": chunk.file_name,
                "chunk_index": chunk.chunk_index,
            }
            # Chroma metadata supports scalar values but not None. DOCX/TXT
            # pages have no page number, so omit the key and restore None when
            # building a SourceReference later.
            if chunk.page is not None:
                metadata["page"] = chunk.page
            metadatas.append(metadata)

        for offset in range(0, len(chunks), MAX_UPSERT_BATCH_SIZE):
            end = offset + MAX_UPSERT_BATCH_SIZE
            self.collection.upsert(
                ids=ids[offset:end],
                embeddings=vectors[offset:end],
                documents=documents[offset:end],
                metadatas=metadatas[offset:end],
            )

        stale_ids = previous_ids - set(ids)
        if stale_ids:
            self.collection.delete(ids=sorted(stale_ids))
        return len(chunks)

    def delete_document(self, *, course_id: str, doc_id: str) -> None:
        """Remove all indexed chunks for one document in one course."""
        self.collection.delete(where=self._document_scope(course_id, doc_id))
