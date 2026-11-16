"""Embedding providers used by the document indexing pipeline."""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import httpx


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot return valid vectors."""


class EmbeddingProvider(Protocol):
    """Small interface shared by document and query embedding providers."""

    @property
    def model_name(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


# Asymmetric retrieval models expect different prompts for queries and
# documents. Keys are the model base name (no namespace, no ":tag").
# Verify against the model card of the exact build you pull with Ollama.
_KNOWN_PROMPTS: dict[str, tuple[str, str]] = {
    # (query_prefix, document_prefix)
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "mxbai-embed-large": ("Represent this sentence for searching relevant passages: ", ""),
}

_ERROR_BODY_LIMIT = 500


def _model_key(model: str) -> str:
    return model.strip().lower().split("/")[-1].split(":")[0]


def _validated_vectors(raw_vectors: object, expected_count: int) -> list[list[float]]:
    if not isinstance(raw_vectors, list) or len(raw_vectors) != expected_count:
        raise EmbeddingError(
            f"Embedding provider returned {len(raw_vectors) if isinstance(raw_vectors, list) else 'an invalid number of'} "
            f"vectors; expected {expected_count}."
        )

    vectors: list[list[float]] = []
    dimensions: int | None = None
    for raw_vector in raw_vectors:
        if not isinstance(raw_vector, list) or not raw_vector:
            raise EmbeddingError("Embedding provider returned an empty or invalid vector.")
        vector: list[float] = []
        for value in raw_vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingError("Embedding vectors must contain only numeric values.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise EmbeddingError("Embedding vectors cannot contain NaN or infinity.")
            vector.append(numeric_value)

        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise EmbeddingError("Embedding provider returned vectors with mixed dimensions.")
        vectors.append(vector)
    return vectors


@dataclass(frozen=True)
class OllamaEmbeddingProvider:
    """Embedding adapter for Ollama's ``POST /api/embed`` endpoint.

    ``query_prefix`` / ``document_prefix``:
      * ``None``  -> use the built-in prompt for known models (default);
      * ``""``    -> explicitly no prefix;
      * any text  -> use it verbatim.
    """

    model: str = "embeddinggemma"
    base_url: str = "http://127.0.0.1:11434"
    batch_size: int = 16
    timeout_seconds: float = 90.0
    query_prefix: str | None = None
    document_prefix: str | None = None
    # Test hook (e.g. ``httpx.MockTransport``); not part of equality or repr.
    transport: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama embedding model must not be empty.")
        if self.batch_size < 1:
            raise ValueError("Embedding batch_size must be at least 1.")
        if self.timeout_seconds <= 0:
            raise ValueError("Embedding timeout_seconds must be positive.")

    @property
    def resolved_query_prefix(self) -> str:
        if self.query_prefix is not None:
            return self.query_prefix
        return _KNOWN_PROMPTS.get(_model_key(self.model), ("", ""))[0]

    @property
    def resolved_document_prefix(self) -> str:
        if self.document_prefix is not None:
            return self.document_prefix
        return _KNOWN_PROMPTS.get(_model_key(self.model), ("", ""))[1]

    @property
    def model_name(self) -> str:
        """Identity of the *embedding space*, used to guard vector stores.

        The prompts change the vectors, so a short digest of them is part of
        the name: indexing with different prefixes must not silently share a
        collection.
        """
        query_prefix = self.resolved_query_prefix
        document_prefix = self.resolved_document_prefix
        if not query_prefix and not document_prefix:
            return f"ollama:{self.model}"
        digest = hashlib.sha256(
            f"{query_prefix}\x1f{document_prefix}".encode("utf-8")
        ).hexdigest()[:8]
        return f"ollama:{self.model}#p{digest}"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Embedding input text must not be empty.")
        prefix = self.resolved_document_prefix
        return self._embed([f"{prefix}{text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Embedding query must not be empty.")
        return self._embed([f"{self.resolved_query_prefix}{text}"])[0]

    def _embed(self, inputs: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        base_url = self.base_url.rstrip("/")
        try:
            with httpx.Client(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                for offset in range(0, len(inputs), self.batch_size):
                    batch = list(inputs[offset:offset + self.batch_size])
                    response = client.post(
                        f"{base_url}/api/embed",
                        json={
                            "model": self.model,
                            "input": batch,
                            # Fail on model context overflow instead of silently
                            # embedding a truncated chunk.
                            "truncate": False,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise EmbeddingError("Ollama returned an invalid JSON response.")
                    batch_vectors = _validated_vectors(
                        payload.get("embeddings"), expected_count=len(batch)
                    )
                    if vectors and len(batch_vectors[0]) != len(vectors[0]):
                        raise EmbeddingError(
                            "Ollama returned different vector dimensions across batches."
                        )
                    vectors.extend(batch_vectors)
        except httpx.HTTPStatusError as exc:
            # The body usually says *why* (unknown model, input longer than the
            # context window with truncate=False, ...). Surface it.
            body = exc.response.text.strip()[:_ERROR_BODY_LIMIT]
            raise EmbeddingError(
                f"Ollama model '{self.model}' returned HTTP "
                f"{exc.response.status_code}: {body or exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError(
                f"Could not create embeddings with Ollama model '{self.model}': {exc}"
            ) from exc
        except ValueError as exc:
            # Includes a non-JSON HTTP body from an unavailable/incompatible
            # Ollama server.
            raise EmbeddingError(
                f"Ollama returned an invalid response for model '{self.model}': {exc}"
            ) from exc

        return vectors


def _env_number(name: str, default: str, cast: type) -> Any:
    raw = os.getenv(name, default).strip()
    try:
        return cast(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name}={raw!r} must be a valid {cast.__name__}.") from exc


def _env_optional_text(name: str) -> str | None:
    """Unset -> None (auto); set (even to "") -> that exact value."""
    return os.environ.get(name)


def create_embedding_provider() -> EmbeddingProvider:
    """Build the configured provider; Ollama is the initial MVP adapter."""
    provider_name = os.getenv("QUIZFORGE_EMBEDDING_PROVIDER", "ollama").strip().lower()
    if provider_name != "ollama":
        raise ValueError(
            f"Unsupported embedding provider '{provider_name}'. Currently supported: ollama."
        )

    return OllamaEmbeddingProvider(
        model=os.getenv("QUIZFORGE_EMBEDDING_MODEL", "embeddinggemma").strip(),
        base_url=os.getenv(
            "QUIZFORGE_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ).strip(),
        batch_size=_env_number("QUIZFORGE_EMBEDDING_BATCH_SIZE", "16", int),
        timeout_seconds=_env_number("QUIZFORGE_EMBEDDING_TIMEOUT_SECONDS", "90", float),
        query_prefix=_env_optional_text("QUIZFORGE_EMBEDDING_QUERY_PREFIX"),
        document_prefix=_env_optional_text("QUIZFORGE_EMBEDDING_DOCUMENT_PREFIX"),
    )
