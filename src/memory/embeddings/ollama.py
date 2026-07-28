import httpx
from memory.embeddings.base import EmbeddingProvider


def _normalize_model_name(name: str) -> str:
    return name.split(":", 1)[0] if name else ""


def is_model_loaded(model: str, base_url: str, timeout: float = 0.5) -> bool:
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/ps", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return False

    models = data.get("models") or []
    target = _normalize_model_name(model)
    for entry in models:
        name = _normalize_model_name(entry.get("name") or entry.get("model") or "")
        if name == target:
            return True
    return False


class OllamaEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "nomic-embed-text",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def embed(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    search = embed
