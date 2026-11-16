import json

import httpx
import pytest

from backend.embeddings import (
    EmbeddingError,
    OllamaEmbeddingProvider,
    create_embedding_provider,
)


def provider_with(handler, **kwargs):
    return OllamaEmbeddingProvider(transport=httpx.MockTransport(handler), **kwargs)


def echo_handler(seen):
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3] for _ in body["input"]]})
    return handler


def test_embeddinggemma_uses_different_prefixes_for_documents_and_queries():
    seen = []
    p = provider_with(echo_handler(seen))
    p.embed_documents(["nội dung"])
    p.embed_query("câu hỏi")
    assert seen[0]["input"] == ["title: none | text: nội dung"]
    assert seen[1]["input"] == ["task: search result | query: câu hỏi"]
    assert seen[0]["truncate"] is False


def test_unknown_model_has_no_prefix_and_plain_name():
    seen = []
    p = provider_with(echo_handler(seen), model="bge-m3")
    p.embed_documents(["abc"])
    assert seen[0]["input"] == ["abc"]
    assert p.model_name == "ollama:bge-m3"


def test_explicit_empty_prefix_overrides_known_model():
    seen = []
    p = provider_with(echo_handler(seen), query_prefix="", document_prefix="")
    p.embed_query("q")
    assert seen[0]["input"] == ["q"]
    assert p.model_name == "ollama:embeddinggemma"


def test_model_name_changes_with_prompts():
    a = OllamaEmbeddingProvider()
    b = OllamaEmbeddingProvider(document_prefix="doc: ")
    assert a.model_name != b.model_name and a.model_name.startswith("ollama:embeddinggemma#p")


def test_http_error_includes_response_body():
    def handler(request):
        return httpx.Response(400, text="the input length exceeds the context length")
    with pytest.raises(EmbeddingError, match="context length"):
        provider_with(handler).embed_documents(["x"])


def test_batches_are_split():
    seen = []
    p = provider_with(echo_handler(seen), batch_size=2)
    vectors = p.embed_documents(["a", "b", "c", "d", "e"])
    assert len(vectors) == 5 and [len(b["input"]) for b in seen] == [2, 2, 1]


def test_wrong_vector_count_is_rejected():
    def handler(request):
        return httpx.Response(200, json={"embeddings": [[0.1]]})
    with pytest.raises(EmbeddingError):
        provider_with(handler).embed_documents(["a", "b"])


def test_empty_inputs_rejected():
    p = OllamaEmbeddingProvider()
    with pytest.raises(ValueError):
        p.embed_documents(["ok", "  "])
    with pytest.raises(ValueError):
        p.embed_query(" ")


def test_bad_env_number_names_the_variable(monkeypatch):
    monkeypatch.setenv("QUIZFORGE_EMBEDDING_BATCH_SIZE", "abc")
    with pytest.raises(ValueError, match="QUIZFORGE_EMBEDDING_BATCH_SIZE"):
        create_embedding_provider()


def test_env_prefix_override(monkeypatch):
    monkeypatch.setenv("QUIZFORGE_EMBEDDING_QUERY_PREFIX", "")
    assert create_embedding_provider().resolved_query_prefix == ""
