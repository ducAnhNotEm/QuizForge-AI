import unicodedata

import pytest

from backend.ingestion import chunk_document, index_document, make_chunk_id
from backend.schemas import ParsedDocument, ParsedPage


def make_doc(*pages, file_name="a.pdf"):
    parsed = [ParsedPage(page=i + 1, text=text) for i, text in enumerate(pages)]
    return ParsedDocument(
        file_name=file_name,
        file_type="pdf",
        sha256="0" * 64,
        pages=parsed,
        total_characters=max(1, sum(len(t.replace(" ", "")) for t in pages)),
    )


LONG = " ".join(f"Câu số {i} nói về khái niệm quan trọng." for i in range(120))


def test_tiny_page_is_skipped_not_fatal():
    doc = make_doc("3", LONG, "Cảm ơn")
    chunks = chunk_document(doc, doc_id="d1", course_id="c1")
    assert chunks, "real content must still be indexed"
    assert {c.page for c in chunks} == {2}


def test_all_tiny_pages_yield_no_chunks():
    assert chunk_document(make_doc("1", "ab"), doc_id="d1", course_id="c1") == []


def test_chunk_id_depends_on_course():
    doc = make_doc(LONG)
    a = chunk_document(doc, doc_id="same", course_id="course-a")
    b = chunk_document(doc, doc_id="same", course_id="course-b")
    assert {c.chunk_id for c in a}.isdisjoint({c.chunk_id for c in b})
    assert [c.chunk_id for c in a] == [c.chunk_id for c in chunk_document(doc, doc_id="same", course_id="course-a")]


def test_chunk_id_has_no_separator_ambiguity():
    assert make_chunk_id("a:b", "c", 1) != make_chunk_id("a", "b:c", 1)


def test_text_is_nfc_normalized():
    nfd = unicodedata.normalize("NFD", "Tiếng Việt có dấu thanh và dấu mũ rất đa dạng.")
    chunks = chunk_document(make_doc(nfd), doc_id="d", course_id="c")
    assert all(unicodedata.is_normalized("NFC", c.content) for c in chunks)
    assert "Tiếng Việt" in chunks[0].content  # composed form


def test_chunks_respect_size_and_index_order():
    chunks = chunk_document(make_doc(LONG), doc_id="d", course_id="c", chunk_size_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


class FakeEmbedder:
    model_name = "fake:model"

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeStore:
    def __init__(self, model="fake:model"):
        self.embedding_model = model
        self.upserts, self.deleted = [], []

    def upsert_chunks(self, chunks, embeddings):
        self.upserts.append((list(chunks), list(embeddings)))
        return len(chunks)

    def delete_document(self, *, course_id, doc_id):
        self.deleted.append((course_id, doc_id))


def test_reindex_to_zero_chunks_deletes_stale_data():
    store = FakeStore()
    result = index_document(make_doc("x"), doc_id="d1", course_id="c1", embedder=FakeEmbedder(), vector_store=store)
    assert result == []
    assert store.deleted == [("c1", "d1")]
    assert store.upserts == []


def test_index_document_upserts_chunks():
    store = FakeStore()
    result = index_document(make_doc(LONG), doc_id="d1", course_id="c1", embedder=FakeEmbedder(), vector_store=store)
    assert result and store.upserts[0][0] == result and store.deleted == []


def test_model_mismatch_fails_before_embedding():
    class Boom(FakeEmbedder):
        def embed_documents(self, texts):
            raise AssertionError("must not embed when the store model differs")

    with pytest.raises(ValueError):
        index_document(make_doc(LONG), doc_id="d", course_id="c", embedder=Boom(), vector_store=FakeStore("other"))
