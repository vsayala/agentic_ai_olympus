from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Protocol, cast

from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]

from olympus_copilot_sdk.vector_db_02.chunking import (
    VECTOR_CHUNK_CHARACTERS,
    VECTOR_CHUNK_OVERLAP,
    VECTOR_CHUNKING_VERSION,
    VECTOR_PARENT_MAX_CHARACTERS,
    VECTOR_PARENT_TARGET_CHARACTERS,
    VectorChunk,
    make_vector_chunks,
)
from olympus_copilot_sdk.vector_db_02.documents import iter_documents
from olympus_copilot_sdk.vector_db_02.embeddings import EmbeddingProvider, FastEmbedProvider
from olympus_copilot_sdk.vector_db_02.retrieval import (
    BROAD_RESULT_LIMIT,
    HYBRID_RETRIEVAL_VERSION,
    IndexSummary,
    SearchResult,
    broad_rank,
    candidate_limit,
    classify_query,
    hybrid_rank,
    is_financial_results_query,
)

COLLECTION_NAME = "olympus_chunks"
INDEX_BATCH_SIZE = 64
MILVUS_SCHEMA_VERSION = "child-parent-location-v1"


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

    def load_collection(self, collection_name: str) -> None: ...

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
        corpus_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", self.data_directory.name)
        default_database_name = (
            "milvus_lite.db" if corpus_name == "data" else f"{corpus_name}.milvus_lite.db"
        )
        self.database_path = database_path or runtime_directory / default_database_name
        self._metadata_path = self.database_path.with_suffix(".metadata.json")
        self._embedding = embedding or FastEmbedProvider(runtime_directory / "models")
        self._client: MilvusLiteClient | None = None
        self._lock = threading.RLock()
        self._chunks: list[VectorChunk] = []
        indexed: list[str] = []
        skipped: list[str] = []
        for source, text in iter_documents(self.data_directory, skipped):
            indexed.append(source)
            self._chunks.extend(make_vector_chunks(source, text, len(self._chunks)))
        self.summary = IndexSummary(tuple(indexed), tuple(skipped), len(self._chunks))
        self._fingerprint = self._content_fingerprint()

    def search(self, query: str, limit: int = 6) -> list[SearchResult]:
        if not query.strip() or not self._chunks or limit <= 0:
            return []
        mode = classify_query(query)
        financial_results = is_financial_results_query(query)
        result_limit = BROAD_RESULT_LIMIT if mode == "broad" or financial_results else limit
        with self._lock:
            client = self._ensure_index()
            query_vector = self._embedding.embed([query])[0]
            try:
                hits = self._search_client(client, query_vector, result_limit)
            except RuntimeError as error:
                if not any(term in str(error).casefold() for term in ("load", "release")):
                    raise
                client.load_collection(COLLECTION_NAME)
                hits = self._search_client(client, query_vector, result_limit)
        dense_results = [
            SearchResult(
                source=str(cast(dict[str, object], hit["entity"])["source"]),
                text=str(cast(dict[str, object], hit["entity"])["text"]),
                score=cast(float, hit["distance"]),
                chunk_id=cast(int, cast(dict[str, object], hit["entity"])["chunk_id"]),
            )
            for hit in hits[0]
        ]
        if mode == "broad" or financial_results:
            return broad_rank(
                query,
                self._chunks,
                dense_results,
                result_limit,
                cover_policy_topics=not financial_results,
            )
        return hybrid_rank(query, self._chunks, dense_results, result_limit)

    def _search_client(
        self,
        client: MilvusLiteClient,
        query_vector: list[float],
        result_limit: int,
    ) -> list[list[dict[str, object]]]:
        return client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=min(len(self._chunks), candidate_limit(result_limit)),
            output_fields=[
                "chunk_id",
                "source",
                "text",
                "page_label",
                "section",
                "parent_id",
                "parent_text",
            ],
            search_params={"metric_type": "COSINE"},
        )

    def close(self) -> None:
        with self._lock:
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
            self._client.load_collection(COLLECTION_NAME)
            return self._client
        if self._client.has_collection(COLLECTION_NAME):
            self._client.drop_collection(COLLECTION_NAME)
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=self._embedding.dimension,
            auto_id=True,
            metric_type="COSINE",
        )
        for start in range(0, len(self._chunks), INDEX_BATCH_SIZE):
            chunks = self._chunks[start : start + INDEX_BATCH_SIZE]
            vectors = self._embedding.embed([chunk.text for chunk in chunks])
            self._client.insert(
                collection_name=COLLECTION_NAME,
                data=[
                    {
                        "vector": vector,
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                        "text": chunk.text,
                        "page_label": chunk.page_label,
                        "section": chunk.section,
                        "parent_id": chunk.parent_id,
                        "parent_text": chunk.parent_text,
                    }
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ],
            )
        self._client.load_collection(COLLECTION_NAME)
        self._write_metadata()
        return self._client

    def _content_fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(MILVUS_SCHEMA_VERSION.encode())
        digest.update(VECTOR_CHUNKING_VERSION.encode())
        digest.update(str(VECTOR_CHUNK_CHARACTERS).encode())
        digest.update(str(VECTOR_CHUNK_OVERLAP).encode())
        digest.update(str(VECTOR_PARENT_TARGET_CHARACTERS).encode())
        digest.update(str(VECTOR_PARENT_MAX_CHARACTERS).encode())
        digest.update(HYBRID_RETRIEVAL_VERSION.encode())
        digest.update(str(candidate_limit(6)).encode())
        for chunk in self._chunks:
            digest.update(str(chunk.chunk_id).encode())
            digest.update(chunk.source.encode())
            digest.update(chunk.text.encode())
            digest.update(chunk.page_label.encode())
            digest.update(chunk.section.encode())
            digest.update(str(chunk.parent_id).encode())
            digest.update(chunk.parent_text.encode())
        return digest.hexdigest()

    def _read_metadata(self) -> dict[str, object]:
        try:
            value = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return cast(dict[str, object], value) if isinstance(value, dict) else {}

    def _write_metadata(self) -> None:
        metadata = {
            "fingerprint": self._fingerprint,
            "model": self._embedding.model_name,
            "schema": MILVUS_SCHEMA_VERSION,
            "chunking": VECTOR_CHUNKING_VERSION,
            "retrieval": HYBRID_RETRIEVAL_VERSION,
        }
        self._metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
