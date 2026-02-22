import pytest
from memory.embeddings.ollama import OllamaEmbedding
from memory.embeddings.openai_embed import OpenAIEmbedding
from memory.embeddings.base import EmbeddingProvider


def test_ollama_is_embedding_provider():
    assert issubclass(OllamaEmbedding, EmbeddingProvider)


def test_openai_is_embedding_provider():
    assert issubclass(OpenAIEmbedding, EmbeddingProvider)


def test_ollama_default_config():
    p = OllamaEmbedding()
    assert p.model == "nomic-embed-text"
    assert p.base_url == "http://localhost:11434"


def test_openai_default_config():
    p = OpenAIEmbedding()
    assert p.model == "text-embedding-3-small"


def test_openai_respects_base_url(monkeypatch):
    import memory.embeddings.openai_embed as openai_embed

    called = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    def fake_post(url, *, headers, json, timeout):
        called["url"] = url
        called["headers"] = headers
        called["json"] = json
        called["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(openai_embed.httpx, "post", fake_post)

    p = OpenAIEmbedding(api_key="k", base_url="https://example.com/v1/")
    out = p.embed("hello")

    assert out == [0.1, 0.2, 0.3]
    assert called["url"] == "https://example.com/v1/embeddings"
    assert called["headers"]["Authorization"] == "Bearer k"
