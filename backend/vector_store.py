"""Persistent ChromaDB storage for page-aware document chunks."""

from __future__ import annotations

import logging
import math
import os
import threading
from pathlib import Path
from typing import Any, Sequence

from backend.schemas import DocumentChunk, RetrievedChunk

logger = logging.getLogger(__name__)

# v2: chunk ids now include course_id and vectors use query/document prompts,
# so v1 data is not compatible. Re-index documents into this collection.
DEFAULT_COLLECTION_NAME = "quizforge_chunks_v2"
SCHEMA_VERSION = 2
DISTANCE_METRIC = "cosine"
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


def _resolve_storage_path(path: str | Path | None) -> Path:
    default_path = Path(__file__).resolve().parent / "data" / "chroma"
    configured_path = path or os.getenv("QUIZFORGE_CHROMA_PATH", str(default_path))
    return Path(configured_path).expanduser().resolve()


def _configured_space(collection: Any) -> str | None:
    """Best-effort read of the distance metric from Chroma's own configuration.

    Newer Chroma versions moved ``hnsw:space`` from collection metadata to a
    ``configuration`` object. The shape differs between releases, so this is
    defensive: ``None`` means "could not tell", never "wrong".
    """
    try:
        config = getattr(collection, "configuration", None)
        if config is None:
            return None
        hnsw = config.get("hnsw") if hasattr(config, "get") else getattr(config, "hnsw", None)
        if hnsw is None:
            return None
        space = hnsw.get("space") if hasattr(hnsw, "get") else getattr(hnsw, "space", None)
        return str(space) if space else None
    except Exception:  # pragma: no cover - depends on the Chroma version
        return None


def _to_retrieved_chunk(
    chunk_id: str,
    content: str,
    metadata: dict[str, Any] | None,
    distance: float | None = None,
) -> RetrievedChunk:
    """Rebuild a ``RetrievedChunk`` from a Chroma row (restoring ``page=None``)."""
    metadata = metadata or {}
    try:
        page = metadata.get("page")
        return RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=str(metadata["doc_id"]),
            course_id=str(metadata["course_id"]),
            file_name=str(metadata["file_name"]),
            page=int(page) if page is not None else None,
            chunk_index=int(metadata["chunk_index"]),
            content=content,
            distance=None if distance is None else float(distance),
            score=None if distance is None else 1.0 - float(distance),
        )
    except KeyError as exc:
        raise ValueError(
            f"Chunk {chunk_id!r} is missing metadata field {exc.args[0]!r}; "
            "was it written by an incompatible schema version?"
        ) from exc


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

            storage_path = _resolve_storage_path(path)
            storage_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(storage_path))

        self.embedding_model = embedding_model
        self.collection_name = (
            collection_name
            or os.getenv("QUIZFORGE_CHROMA_COLLECTION", DEFAULT_COLLECTION_NAME)
        )
        self.client = client
        self.collection = self._open_collection()
        self._verify_collection()

    # ------------------------------------------------------------------ setup

    def _open_collection(self) -> Any:
        # Our own `distance_metric` key is plain metadata and survives every
        # Chroma version, so the cosine guarantee never depends on whether the
        # engine still understands the legacy "hnsw:space" key.
        base_metadata = {
            "embedding_model": self.embedding_model,
            "distance_metric": DISTANCE_METRIC,
            "schema_version": SCHEMA_VERSION,
        }
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={**base_metadata, "hnsw:space": DISTANCE_METRIC},
                # Embeddings come from the configured provider and are passed
                # explicitly; Chroma must not silently choose another model.
                embedding_function=None,
            )
        except Exception as legacy_exc:
            logger.warning(
                "Creating the collection with legacy 'hnsw:space' metadata failed "
                "(%s); retrying with the newer `configuration` argument.",
                legacy_exc,
            )
            try:
                return self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata=base_metadata,
                    configuration={"hnsw": {"space": DISTANCE_METRIC}},
                    embedding_function=None,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not create ChromaDB collection '{self.collection_name}' "
                    "with cosine distance using either the legacy metadata or the "
                    "newer configuration API. Pin a tested chromadb version."
                ) from exc

    def _verify_collection(self) -> None:
        metadata = dict(self.collection.metadata or {})

        stored_model = metadata.get("embedding_model")
        if stored_model != self.embedding_model:
            raise ValueError(
                f"Collection '{self.collection_name}' uses embedding model "
                f"{stored_model!r}; configured model is {self.embedding_model!r}. "
                "Use a new collection and re-index documents when changing models."
            )

        # Every source that is present must say "cosine"; at least one must exist.
        declared = {
            "metadata 'distance_metric'": metadata.get("distance_metric"),
            "metadata 'hnsw:space'": metadata.get("hnsw:space"),
            "collection configuration": _configured_space(self.collection),
        }
        present = {source: value for source, value in declared.items() if value is not None}
        if not present:
            raise ValueError(
                f"Cannot confirm that collection '{self.collection_name}' uses cosine "
                "distance. Use a new collection and re-index documents."
            )
        for source, value in present.items():
            if value != DISTANCE_METRIC:
                raise ValueError(
                    f"Collection '{self.collection_name}' must use cosine distance, "
                    f"but {source} says {value!r}. Use a new collection and re-index "
                    "documents to change the metric."
                )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _build_where(conditions: list[dict]) -> dict:
        return conditions[0] if len(conditions) == 1 else {"$and": conditions}

    @staticmethod
    def _document_scope(course_id: str, doc_id: str) -> dict:
        return {
            "$and": [
                {"course_id": course_id},
                {"doc_id": doc_id},
            ]
        }

    # ------------------------------------------------------------------ write

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
        if not course_id.strip():
            raise ValueError("course_id must not be empty.")
        if not doc_id.strip():
            raise ValueError("doc_id must not be empty.")
        self.collection.delete(where=self._document_scope(course_id, doc_id))

    # ------------------------------------------------------------------- read

    def query_chunks(
        self,
        *,
        query_embedding: Sequence[float],
        course_id: str,
        top_k: int,
        doc_id: str | None = None,
    ) -> dict[str, Any]:
        """Query chunks within one course, optionally limited to one document.

        Returns Chroma's raw result dict. Prefer :meth:`search` for typed
        results. The course filter is applied by ChromaDB itself rather than
        after a global query, preventing cross-course results from reaching
        callers.
        """
        if not course_id.strip():
            raise ValueError("course_id must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if not query_embedding:
            raise ValueError("query_embedding must not be empty.")
        if doc_id is not None and not doc_id.strip():
            raise ValueError("doc_id must not be empty when provided.")

        where = (
            {"course_id": course_id}
            if doc_id is None
            else self._document_scope(course_id, doc_id)
        )
        return self.collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def search(
        self,
        *,
        query_embedding: Sequence[float],
        course_id: str,
        top_k: int,
        doc_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Similarity search returning typed chunks, best match first."""
        raw = self.query_chunks(
            query_embedding=query_embedding,
            course_id=course_id,
            top_k=top_k,
            doc_id=doc_id,
        )
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        return [
            _to_retrieved_chunk(chunk_id, content, metadata, distance)
            for chunk_id, content, metadata, distance in zip(ids, documents, metadatas, distances)
        ]

    def get_chunks(
        self,
        *,
        course_id: str,
        doc_id: str | None = None,
        chunk_ids: Sequence[str] | None = None,
        min_chunk_index: int | None = None,
        max_chunk_index: int | None = None,
    ) -> list[RetrievedChunk]:
        """Fetch chunks by filter (no similarity), ordered by (doc_id, chunk_index).

        Always scoped to ``course_id``. Useful for "all chunks of this
        document", "chunks N..M", or sampling evenly across a document.
        """
        if not course_id.strip():
            raise ValueError("course_id must not be empty.")
        if doc_id is not None and not doc_id.strip():
            raise ValueError("doc_id must not be empty when provided.")
        if chunk_ids is not None and not chunk_ids:
            return []

        conditions: list[dict] = [{"course_id": course_id}]
        if doc_id is not None:
            conditions.append({"doc_id": doc_id})
        if min_chunk_index is not None:
            conditions.append({"chunk_index": {"$gte": min_chunk_index}})
        if max_chunk_index is not None:
            conditions.append({"chunk_index": {"$lte": max_chunk_index}})

        kwargs: dict[str, Any] = {
            "where": self._build_where(conditions),
            "include": ["documents", "metadatas"],
        }
        if chunk_ids is not None:
            kwargs["ids"] = list(chunk_ids)

        raw = self.collection.get(**kwargs)
        chunks = [
            _to_retrieved_chunk(chunk_id, content, metadata)
            for chunk_id, content, metadata in zip(
                raw.get("ids") or [], raw.get("documents") or [], raw.get("metadatas") or []
            )
        ]
        chunks.sort(key=lambda chunk: (chunk.doc_id, chunk.chunk_index))
        return chunks

    def get_neighbors(
        self,
        *,
        course_id: str,
        doc_id: str,
        chunk_index: int,
        window: int = 1,
        include_self: bool = False,
    ) -> list[RetrievedChunk]:
        """Chunks within ``window`` positions of ``chunk_index`` in the same document.

        ``chunk_index`` is document-wide (it keeps counting across pages), so
        neighbours may come from the next or previous page.
        """
        if window < 1:
            raise ValueError("window must be at least 1.")
        chunks = self.get_chunks(
            course_id=course_id,
            doc_id=doc_id,
            min_chunk_index=max(0, chunk_index - window),
            max_chunk_index=chunk_index + window,
        )
        if include_self:
            return chunks
        return [chunk for chunk in chunks if chunk.chunk_index != chunk_index]


# ---------------------------------------------------------------- shared store

_STORE_CACHE: dict[tuple[str, str, str], ChromaVectorStore] = {}
_STORE_LOCK = threading.Lock()


def get_vector_store(
    embedding_model: str,
    *,
    path: str | Path | None = None,
    collection_name: str | None = None,
) -> ChromaVectorStore:
    """Return one shared store per (path, collection, model) in this process.

    Avoids opening a new ``PersistentClient`` on every ``index_document`` call.
    The cache is per process: with several worker processes writing to one
    on-disk Chroma directory, SQLite locking can still bite; use a Chroma
    server (HttpClient) in that setup.
    """
    resolved_path = _resolve_storage_path(path)
    name = collection_name or os.getenv("QUIZFORGE_CHROMA_COLLECTION", DEFAULT_COLLECTION_NAME)
    key = (str(resolved_path), name, embedding_model)
    with _STORE_LOCK:
        store = _STORE_CACHE.get(key)
        if store is None:
            store = ChromaVectorStore(
                embedding_model=embedding_model,
                path=resolved_path,
                collection_name=name,
            )
            _STORE_CACHE[key] = store
        return store


def reset_vector_store_cache() -> None:
    """Forget cached stores (tests, or after deleting the Chroma directory)."""
    with _STORE_LOCK:
        _STORE_CACHE.clear()
