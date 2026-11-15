"""Embedding providers used by the document indexing pipeline."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Protocol, Sequence

import httpx


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot return valid vectors."""


class EmbeddingProvider(Protocol):
    """Small interface shared by document and query embedding providers."""

    @property
    def model_name(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


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
    """Embedding adapter for Ollama's ``POST /api/embed`` endpoint."""

    model: str = "embeddinggemma"
    base_url: str = "http://127.0.0.1:11434"
    batch_size: int = 16
    timeout_seconds: float = 90.0

    @property
    def model_name(self) -> str:
        return f"ollama:{self.model}"

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama embedding model must not be empty.")
        if self.batch_size < 1:
            raise ValueError("Embedding batch_size must be at least 1.")
        if self.timeout_seconds <= 0:
            raise ValueError("Embedding timeout_seconds must be positive.")

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Embedding input text must not be empty.")

        vectors: list[list[float]] = []
        base_url = self.base_url.rstrip("/")
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                for offset in range(0, len(texts), self.batch_size):
                    batch = list(texts[offset:offset + self.batch_size])
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

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Embedding query must not be empty.")
        return self.embed_documents([text])[0]


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
        batch_size=int(os.getenv("QUIZFORGE_EMBEDDING_BATCH_SIZE", "16")),
        timeout_seconds=float(os.getenv("QUIZFORGE_EMBEDDING_TIMEOUT_SECONDS", "90")),
    )
