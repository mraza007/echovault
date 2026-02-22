import httpx
from memory.embeddings.base import EmbeddingProvider


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def embed(self, text: str) -> list[float]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
