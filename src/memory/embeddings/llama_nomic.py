import httpx
from memory.embeddings.base import EmbeddingProvider


class LlamaNomicEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "text-embedder",
                 base_url: str = "http://localhost:11435"):
        self.model = model
        self.base_url = base_url

    def embed(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "content": 'search_document: ' + text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()[0]["embedding"][0]

    def search(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "content": 'search_query: ' + text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()[0]["embedding"][0]
