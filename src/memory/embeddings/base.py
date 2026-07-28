from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def search(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
