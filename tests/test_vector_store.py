"""Integration tests against a real (temporary, on-disk) ChromaDB.

Skipped automatically when chromadb is not installed. Run these after
installing or upgrading chromadb: they are the check that the collection
really uses cosine distance on *your* Chroma version.
"""

import pytest

pytest.importorskip("chromadb")

from backend.ingestion import make_chunk_id
from backend.schemas import DocumentChunk
from backend.vector_store import ChromaVectorStore, get_vector_store, reset_vector_store_cache

MODEL = "test:model"


@pytest.fixture()
def store(tmp_path):
    return ChromaVectorStore(embedding_model=MODEL, path=tmp_path, collection_name="t_chunks")


def chunk(i, *, doc="d1", course="c1", page=1):
    return DocumentChunk(
        chunk_id=make_chunk_id(course, doc, i), doc_id=doc, course_id=course, file_name="a.pdf",
        page=page, content=f"nội dung của đoạn số {i}", chunk_index=i,
    )


def test_collection_really_uses_cosine_distance(store):
    store.upsert_chunks([chunk(0), chunk(1)], [[1.0, 0.0], [0.0, 1.0]])
    hits = store.search(query_embedding=[2.0, 0.0], course_id="c1", top_k=2)  # scaled: cosine ignores length
    assert hits[0].chunk_index == 0 and hits[0].distance == pytest.approx(0.0, abs=1e-4)
    assert hits[1].distance == pytest.approx(1.0, abs=1e-4)       # orthogonal -> 1 in cosine
    assert hits[0].score == pytest.approx(1.0, abs=1e-4)


def test_course_isolation_even_with_same_doc_id(store):
    store.upsert_chunks([chunk(0, course="c1")], [[1.0, 0.0]])
    store.upsert_chunks([chunk(0, course="c2")], [[1.0, 0.0]])
    assert len(store.search(query_embedding=[1.0, 0.0], course_id="c1", top_k=5)) == 1
    assert len(store.search(query_embedding=[1.0, 0.0], course_id="c2", top_k=5)) == 1


def test_reupsert_removes_stale_chunks_and_delete_document_works(store):
    store.upsert_chunks([chunk(i) for i in range(3)], [[1.0, 0.0]] * 3)
    store.upsert_chunks([chunk(0)], [[1.0, 0.0]])
    assert [c.chunk_index for c in store.get_chunks(course_id="c1", doc_id="d1")] == [0]
    store.delete_document(course_id="c1", doc_id="d1")
    assert store.get_chunks(course_id="c1", doc_id="d1") == []


def test_page_none_round_trips(store):
    store.upsert_chunks([chunk(0, page=None)], [[1.0, 0.0]])
    assert store.get_chunks(course_id="c1")[0].page is None


def test_get_neighbors_in_reading_order(store):
    store.upsert_chunks([chunk(i) for i in range(6)], [[1.0, 0.0]] * 6)
    assert [c.chunk_index for c in store.get_neighbors(course_id="c1", doc_id="d1", chunk_index=3, window=2)] == [1, 2, 4, 5]
    assert [c.chunk_index for c in store.get_neighbors(course_id="c1", doc_id="d1", chunk_index=0, window=1)] == [1]


def test_get_chunks_by_ids_is_still_course_scoped(store):
    store.upsert_chunks([chunk(0, course="c1")], [[1.0, 0.0]])
    other = chunk(0, course="c2")
    store.upsert_chunks([other], [[1.0, 0.0]])
    assert store.get_chunks(course_id="c1", chunk_ids=[other.chunk_id]) == []


def test_model_mismatch_is_rejected(tmp_path):
    ChromaVectorStore(embedding_model=MODEL, path=tmp_path, collection_name="x")
    with pytest.raises(ValueError, match="embedding model"):
        ChromaVectorStore(embedding_model="other:model", path=tmp_path, collection_name="x")


def test_get_vector_store_is_cached(tmp_path):
    reset_vector_store_cache()
    a = get_vector_store(MODEL, path=tmp_path, collection_name="shared")
    assert a is get_vector_store(MODEL, path=tmp_path, collection_name="shared")
    reset_vector_store_cache()
