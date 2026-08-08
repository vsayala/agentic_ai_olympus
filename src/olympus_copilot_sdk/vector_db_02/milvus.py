from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol, cast

from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]

from olympus_copilot_sdk.vector_db_02.chunking import (
    VECTOR_CHUNK_CHARACTERS,
    VECTOR_CHUNK_OVERLAP,
    VectorChunk,
    make_vector_chunks,
)
from olympus_copilot_sdk.vector_db_02.documents import iter_documents
from olympus_copilot_sdk.vector_db_02.embeddings import EmbeddingProvider, FastEmbedProvider
from olympus_copilot_sdk.vector_db_02.retrieval import IndexSummary, SearchResult

COLLECTION_NAME = "olympus_chunks"


class MilvusLiteClient(Protocol):
    def has_collection(self, collection_name: str) -> bool: ...

    def drop_collection(self, collection_name: str) -> None: ...

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        auto_id: bool,
        metric_type: str,
    ) -> None: ...

    def insert(self, collection_name: str, data: list[dict[str, object]]) -> object: ...

    def search(
        self,
        collection_name: str,
        data: list[list[float]],
        limit: int,
        output_fields: list[str],
        search_params: dict[str, object],
    ) -> list[list[dict[str, object]]]: ...

    def close(self) -> None: ...


def _connect(database_path: Path) -> MilvusLiteClient:
    return cast(MilvusLiteClient, MilvusClient(uri=str(database_path)))


class VectorKnowledgeBase:
    def __init__(
        self,
        data_directory: Path,
        database_path: Path | None = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self.data_directory = data_directory.resolve()
        runtime_directory = self.data_directory.parent / ".olympus"
        self.database_path = database_path or runtime_directory / "milvus_lite.db"
        self._metadata_path = self.database_path.with_suffix(".metadata.json")
        self._embedding = embedding or FastEmbedProvider(runtime_directory / "models")
        self._client: MilvusLiteClient | None = None
        self._chunks: list[VectorChunk] = []
        indexed: list[str] = []
        skipped: list[str] = []
        for source, text in iter_documents(self.data_directory, skipped):
            indexed.append(source)
            self._chunks.extend(make_vector_chunks(source, text, len(self._chunks)))
        self.summary = IndexSummary(tuple(indexed), tuple(skipped), len(self._chunks))
        self._fingerprint = self._content_fingerprint()

    def search(self, query: str, limit: int = 6) -> list[SearchResult]:
        if not query.strip() or not self._chunks:
            return []
        client = self._ensure_index()
        query_vector = self._embedding.embed([query])[0]
        hits = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=limit,
            output_fields=["source", "text"],
            search_params={"metric_type": "COSINE"},
        )
        return [
            SearchResult(
                source=str(cast(dict[str, object], hit["entity"])["source"]),
                text=str(cast(dict[str, object], hit["entity"])["text"]),
                score=cast(float, hit["distance"]),
            )
            for hit in hits[0]
        ]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _ensure_index(self) -> MilvusLiteClient:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self._client is None:
            self._client = _connect(self.database_path)
        metadata = self._read_metadata()
        is_current = (
            metadata.get("fingerprint") == self._fingerprint
            and metadata.get("model") == self._embedding.model_name
            and self._client.has_collection(COLLECTION_NAME)
        )
        if is_current:
            return self._client
        if self._client.has_collection(COLLECTION_NAME):
            self._client.drop_collection(COLLECTION_NAME)
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=self._embedding.dimension,
            auto_id=True,
            metric_type="COSINE",
        )
        vectors = self._embedding.embed([chunk.text for chunk in self._chunks])
        self._client.insert(
            collection_name=COLLECTION_NAME,
            data=[
                {"vector": vector, "source": chunk.source, "text": chunk.text}
                for chunk, vector in zip(self._chunks, vectors, strict=True)
            ],
        )
        self._write_metadata()
        return self._client

    def _content_fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(str(VECTOR_CHUNK_CHARACTERS).encode())
        digest.update(str(VECTOR_CHUNK_OVERLAP).encode())
        for chunk in self._chunks:
            digest.update(chunk.source.encode())
            digest.update(chunk.text.encode())
        return digest.hexdigest()

    def _read_metadata(self) -> dict[str, object]:
        try:
            value = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return cast(dict[str, object], value) if isinstance(value, dict) else {}

    def _write_metadata(self) -> None:
        metadata = {"fingerprint": self._fingerprint, "model": self._embedding.model_name}
        self._metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
