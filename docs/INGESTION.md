# Document Embedding and Vector Storage

This is the SV2 ingestion pipeline after SV1 has parsed an uploaded document:

```text
ParsedDocument -> chunk_document() -> Ollama embeddings -> ChromaDB
```

`backend.ingestion.index_document()` performs these steps and returns the
`DocumentChunk` objects it indexed. The function is synchronous so an upload
route or background worker can call it directly; a FastAPI route should run
long-running indexing outside the request handler.

## Setup

Install the backend requirements and make sure Ollama is running with an
embedding model available. The default model is `embeddinggemma`:

```powershell
python -m pip install -r backend/requirements.txt
ollama pull embeddinggemma
```

The following environment variables are optional; these defaults are used if
they are omitted:

| Variable | Default | Purpose |
|---|---|---|
| `QUIZFORGE_EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `QUIZFORGE_EMBEDDING_MODEL` | `embeddinggemma` | Ollama embedding model |
| `QUIZFORGE_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server address |
| `QUIZFORGE_EMBEDDING_BATCH_SIZE` | `16` | Chunks per embedding request |
| `QUIZFORGE_EMBEDDING_TIMEOUT_SECONDS` | `90` | Request timeout |
| `QUIZFORGE_CHROMA_PATH` | `backend/data/chroma` | Persistent Chroma data directory |
| `QUIZFORGE_CHROMA_COLLECTION` | `quizforge_chunks_v1` | Chroma collection name |

Chroma data is stored locally under `backend/data/chroma`, which is ignored by
Git through the existing `data/` ignore rule.

## Calling the pipeline

The future upload or document worker can call the pipeline after assigning a
document ID and course ID:

```python
from backend.documents import parse_document
from backend.ingestion import index_document

parsed = parse_document(upload_path)
chunks = index_document(
    parsed,
    doc_id=document_id,
    course_id=course_id,
)
```

`index_document()` calls the existing chunker, embeds each chunk with the same
configured model in batches, then upserts the vectors into Chroma. It validates
that the embedding count matches the chunk count before writing.

## Chroma record shape

Each record uses `chunk_id` as its Chroma ID and stores `content` as the
document. Metadata includes `course_id`, `doc_id`, `chunk_id`, `file_name`, and
`chunk_index`. It includes `page` for PDF pages; for DOCX/TXT pages, where the
parser supplies `None`, the key is omitted because Chroma metadata uses scalar
values rather than Python `None`.

The collection records the embedding model and cosine distance setting. If the
configured model differs from the model already associated with that
collection, initialization fails with a message to use a new collection and
re-index. This prevents vectors from incompatible embedding spaces from being
mixed.

When a document is re-indexed, existing chunk IDs are upserted and any stale
IDs left from the previous version are removed. Future retrieval code must
embed queries with the same model and always filter the collection by
`course_id` before returning source chunks to SV3.
