"""Unit tests for SV3 course-scoped retrieval and citation packaging."""

from __future__ import annotations

import pytest

from backend.retrieval import CourseRetriever, RetrievalError
from backend.vector_store import ChromaVectorStore


class FakeEmbedder:
    model_name = "test-embedding-v1"

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class FakeStore:
    embedding_model = "test-embedding-v1"

    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[dict] = []

    def query_chunks(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _result(*rows: tuple[str, dict, float]) -> dict:
    return {
        "documents": [[row[0] for row in rows]],
        "metadatas": [[row[1] for row in rows]],
        "distances": [[row[2] for row in rows]],
    }


def _retriever(result: dict) -> tuple[CourseRetriever, FakeEmbedder, FakeStore]:
    embedder = FakeEmbedder()
    store = FakeStore(result)
    return CourseRetriever(embedder=embedder, vector_store=store), embedder, store


def test_retrieval_applies_course_scope_and_builds_citations() -> None:
    retriever, embedder, store = _retriever(
        _result(
            (
                "Binary search has O(log n) complexity.",
                {
                    "course_id": "algorithms",
                    "doc_id": "doc-1",
                    "file_name": "algorithms.pdf",
                    "page": 12,
                },
                0.18,
            ),
            (
                "This row must be rejected defensively.",
                {
                    "course_id": "databases",
                    "doc_id": "doc-2",
                    "file_name": "databases.pdf",
                    "page": 4,
                },
                0.10,
            ),
        )
    )

    result = retriever.retrieve(
        query="What is binary search complexity?",
        course_id="algorithms",
        top_k=3,
        max_distance=0.45,
    )

    assert embedder.queries == ["What is binary search complexity?"]
    assert len(store.calls) == 1
    assert store.calls[0]["course_id"] == "algorithms"
    assert store.calls[0]["top_k"] == 3
    assert store.calls[0]["query_embedding"] == [0.1, 0.2, 0.3]
    assert len(result.matches) == 1
    assert result.matches[0].doc_id == "doc-1"
    assert result.matches[0].file_name == "algorithms.pdf"
    assert result.matches[0].page == 12
    assert result.matches[0].snippet == "Binary search has O(log n) complexity."


def test_retrieval_filters_distance_and_preserves_store_order() -> None:
    retriever, _, _ = _retriever(
        _result(
            (
                "nearest",
                {"course_id": "course-a", "doc_id": "a", "file_name": "a.txt"},
                0.10,
            ),
            (
                "outside threshold",
                {"course_id": "course-a", "doc_id": "b", "file_name": "b.txt"},
                0.51,
            ),
            (
                "second accepted",
                {"course_id": "course-a", "doc_id": "c", "file_name": "c.txt"},
                0.40,
            ),
        )
    )

    result = retriever.retrieve(
        query="query", course_id="course-a", max_distance=0.50
    )

    assert [match.doc_id for match in result.matches] == ["a", "c"]
    assert all(match.page is None for match in result.matches)


def test_retrieval_can_scope_to_a_single_document() -> None:
    retriever, _, store = _retriever(_result())

    retriever.retrieve(
        query="query",
        course_id="course-a",
        doc_id="doc-7",
    )

    assert store.calls[0]["doc_id"] == "doc-7"


def test_retrieval_returns_empty_matches_when_nothing_passes_threshold() -> None:
    retriever, _, _ = _retriever(
        _result(
            (
                "unrelated",
                {"course_id": "course-a", "doc_id": "doc", "file_name": "x.pdf"},
                0.99,
            )
        )
    )

    result = retriever.retrieve(query="query", course_id="course-a")

    assert result.course_id == "course-a"
    assert result.query == "query"
    assert result.matches == []


@pytest.mark.parametrize(
    ("query", "course_id"),
    [("", "course-a"), ("   ", "course-a"), ("query", ""), ("query", "   ")],
)
def test_retrieval_rejects_empty_query_or_course(query: str, course_id: str) -> None:
    retriever, _, _ = _retriever(_result())

    with pytest.raises(ValueError):
        retriever.retrieve(query=query, course_id=course_id)


def test_retrieval_rejects_invalid_parameters() -> None:
    retriever, _, _ = _retriever(_result())

    with pytest.raises(ValueError):
        retriever.retrieve(query="q", course_id="course-a", top_k=0)
    with pytest.raises(ValueError):
        retriever.retrieve(query="q", course_id="course-a", max_distance=-0.1)
    with pytest.raises(ValueError):
        retriever.retrieve(query="q", course_id="course-a", doc_id=" ")


def test_retrieval_requires_same_embedding_model() -> None:
    embedder = FakeEmbedder()
    store = FakeStore(_result())
    store.embedding_model = "different-model"

    with pytest.raises(ValueError, match="same embedding model"):
        CourseRetriever(embedder=embedder, vector_store=store)


def test_retrieval_skips_malformed_rows_without_fabricating_citations() -> None:
    retriever, _, _ = _retriever(
        _result(
            (
                "valid",
                {"course_id": "course-a", "doc_id": "doc", "file_name": "x.txt"},
                0.1,
            ),
            (
                "missing document id",
                {"course_id": "course-a", "file_name": "x.txt"},
                0.1,
            ),
            (
                "bad page",
                {
                    "course_id": "course-a",
                    "doc_id": "doc-2",
                    "file_name": "x.txt",
                    "page": 0,
                },
                0.1,
            ),
        )
    )

    result = retriever.retrieve(query="query", course_id="course-a")

    assert [match.doc_id for match in result.matches] == ["doc"]


def test_retrieval_reports_malformed_vector_store_shape() -> None:
    retriever, _, _ = _retriever(
        {
            "documents": [["text"]],
            "metadatas": [[]],
            "distances": [[0.1]],
        }
    )

    with pytest.raises(RetrievalError, match="mismatched"):
        retriever.retrieve(query="query", course_id="course-a")


def test_vector_store_query_delegates_course_filter_and_options() -> None:
    class Collection:
        def __init__(self) -> None:
            self.arguments = None

        def query(self, **kwargs):
            self.arguments = kwargs
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    collection = Collection()
    store = object.__new__(ChromaVectorStore)
    store.collection = collection

    store.query_chunks(
        query_embedding=[0.1, 0.2],
        course_id="course-a",
        top_k=4,
    )
    assert collection.arguments["where"] == {"course_id": "course-a"}
    assert collection.arguments["n_results"] == 4
    assert collection.arguments["include"] == ["documents", "metadatas", "distances"]

    store.query_chunks(
        query_embedding=[0.1, 0.2],
        course_id="course-a",
        doc_id="doc-1",
        top_k=2,
    )
    assert collection.arguments["where"] == {
        "$and": [{"course_id": "course-a"}, {"doc_id": "doc-1"}]
    }
