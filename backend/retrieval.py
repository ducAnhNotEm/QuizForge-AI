"""Course-scoped semantic retrieval and citation packaging for M2.C.

The retriever deliberately delegates course filtering to the vector store.  A
query is never executed against the whole collection and filtered afterwards;
this keeps course isolation enforced at the database boundary as well as in
Python's defensive validation layer.
"""

from __future__ import annotations

import math
from typing import Any, Protocol, Sequence

from backend.schemas import RetrievalResult, SourceReference


DEFAULT_TOP_K = 5
DEFAULT_MAX_DISTANCE = 0.45


class RetrievalError(RuntimeError):
    """Raised when indexed data cannot be converted into a citation safely."""


class QueryEmbedder(Protocol):
    model_name: str

    def embed_query(self, text: str) -> list[float]: ...


class RetrievalStore(Protocol):
    embedding_model: str

    def query_chunks(
        self,
        *,
        query_embedding: Sequence[float],
        course_id: str,
        top_k: int,
        doc_id: str | None = None,
    ) -> dict[str, Any]: ...


class CourseRetriever:
    """Retrieve relevant chunks from exactly one course and cite their origin."""

    def __init__(
        self,
        *,
        embedder: QueryEmbedder,
        vector_store: RetrievalStore,
        default_max_distance: float = DEFAULT_MAX_DISTANCE,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.default_max_distance = self._validate_distance(
            default_max_distance, name="default_max_distance"
        )

        embedder_model = getattr(embedder, "model_name", None)
        store_model = getattr(vector_store, "embedding_model", None)
        if not isinstance(embedder_model, str) or not embedder_model.strip():
            raise ValueError("embedder.model_name must not be empty.")
        if not isinstance(store_model, str) or not store_model.strip():
            raise ValueError("vector_store.embedding_model must not be empty.")
        if embedder_model != store_model:
            raise ValueError(
                "The query embedder and vector store must use the same embedding model."
            )

    @staticmethod
    def _validate_distance(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite non-negative number.")
        distance = float(value)
        if not math.isfinite(distance) or distance < 0:
            raise ValueError(f"{name} must be a finite non-negative number.")
        return distance

    @staticmethod
    def _validate_result_rows(raw_results: object) -> tuple[list[Any], list[Any], list[Any]]:
        if not isinstance(raw_results, dict):
            raise RetrievalError("Vector store returned an invalid result object.")

        documents = raw_results.get("documents")
        metadatas = raw_results.get("metadatas")
        distances = raw_results.get("distances")
        if not isinstance(documents, list) or not isinstance(metadatas, list):
            raise RetrievalError("Vector store result is missing documents or metadatas.")

        # Chroma returns one nested list because one query embedding is sent.
        documents = documents[0] if documents and isinstance(documents[0], list) else documents
        metadatas = metadatas[0] if metadatas and isinstance(metadatas[0], list) else metadatas
        if distances is None:
            distances = []
        elif isinstance(distances, list) and distances and isinstance(distances[0], list):
            distances = distances[0]
        if not isinstance(distances, list):
            raise RetrievalError("Vector store returned invalid distances.")
        if len(documents) != len(metadatas):
            raise RetrievalError("Vector store returned mismatched documents and metadata.")
        if distances and len(distances) != len(documents):
            raise RetrievalError("Vector store returned mismatched distances.")
        return documents, metadatas, distances

    def retrieve(
        self,
        *,
        query: str,
        course_id: str,
        top_k: int = DEFAULT_TOP_K,
        max_distance: float | None = None,
        doc_id: str | None = None,
    ) -> RetrievalResult:
        """Return thresholded source references for one course-scoped query."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be empty.")
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("course_id must not be empty.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")
        if doc_id is not None and (not isinstance(doc_id, str) or not doc_id.strip()):
            raise ValueError("doc_id must not be empty when provided.")

        threshold = (
            self.default_max_distance
            if max_distance is None
            else self._validate_distance(max_distance, name="max_distance")
        )
        query_embedding = self.embedder.embed_query(query.strip())
        if not isinstance(query_embedding, list) or not query_embedding:
            raise RetrievalError("Embedding provider returned an invalid query vector.")

        raw_results = self.vector_store.query_chunks(
            query_embedding=query_embedding,
            course_id=course_id.strip(),
            top_k=top_k,
            doc_id=doc_id.strip() if doc_id is not None else None,
        )
        documents, metadatas, distances = self._validate_result_rows(raw_results)

        matches: list[SourceReference] = []
        for index, (document, metadata) in enumerate(zip(documents, metadatas)):
            distance = distances[index] if distances else 0.0
            if isinstance(distance, bool) or not isinstance(distance, (int, float)):
                raise RetrievalError("Vector store returned a non-numeric distance.")
            distance = float(distance)
            if not math.isfinite(distance):
                raise RetrievalError("Vector store returned a non-finite distance.")
            if distance > threshold:
                continue
            if not isinstance(document, str) or not document.strip():
                continue
            if not isinstance(metadata, dict):
                continue

            # Defense in depth: the store must filter, and the retriever also
            # refuses to cite a row that claims to belong to another course.
            if metadata.get("course_id") != course_id.strip():
                continue
            source_doc_id = metadata.get("doc_id")
            file_name = metadata.get("file_name")
            if not isinstance(source_doc_id, str) or not source_doc_id.strip():
                continue
            if not isinstance(file_name, str) or not file_name.strip():
                continue

            page = metadata.get("page")
            if page is not None and (
                isinstance(page, bool) or not isinstance(page, int) or page < 1
            ):
                continue
            matches.append(
                SourceReference(
                    doc_id=source_doc_id,
                    file_name=file_name,
                    page=page,
                    snippet=document.strip(),
                )
            )

        return RetrievalResult(
            course_id=course_id.strip(),
            query=query.strip(),
            matches=matches,
        )


def retrieve_course_context(
    *,
    query: str,
    course_id: str,
    embedder: QueryEmbedder,
    vector_store: RetrievalStore,
    top_k: int = DEFAULT_TOP_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    doc_id: str | None = None,
) -> RetrievalResult:
    """Convenience wrapper for callers that do not need a retriever instance."""
    retriever = CourseRetriever(
        embedder=embedder,
        vector_store=vector_store,
        default_max_distance=max_distance,
    )
    return retriever.retrieve(
        query=query,
        course_id=course_id,
        top_k=top_k,
        doc_id=doc_id,
    )
