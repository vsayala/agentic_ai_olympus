from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from fastembed import TextEmbedding

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSION = 384


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedProvider:
    def __init__(
        self,
        cache_directory: Path,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self._cache_directory = cache_directory
        self._model_name = model_name
        self._model: TextEmbedding | None = None

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            self._cache_directory.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(
                model_name=self._model_name,
                cache_dir=str(self._cache_directory),
            )
        vectors = self._model.embed(texts)
        return [cast(list[float], vector.tolist()) for vector in vectors]
