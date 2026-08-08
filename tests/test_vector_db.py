from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from olympus_copilot_sdk.vector_db_02 import milvus
from olympus_copilot_sdk.vector_db_02.chunking import (
    VECTOR_PARENT_MAX_CHARACTERS,
    VECTOR_PARENT_TARGET_CHARACTERS,
    VectorChunk,
    make_vector_chunks,
)
from olympus_copilot_sdk.vector_db_02.milvus import MilvusLiteClient, VectorKnowledgeBase
from olympus_copilot_sdk.vector_db_02.retrieval import (
    POLICY_TOPIC_PATTERNS,
    SearchResult,
    broad_rank,
    classify_query,
    hybrid_rank,
)


@dataclass(frozen=True)
class DeterministicEmbedding:
    dimension: int = 2
    model_name: str = "deterministic-test-embedding"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "river" in text.lower() else [0.0, 1.0] for text in texts]


class CountingEmbedding:
    dimension = 2

    def __init__(self, model_name: str = "counting-model-a") -> None:
        self.model_name = model_name
        self.batch_sizes: list[int] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[1.0, 0.0] for _ in texts]


class ReleasableMilvusClient:
    def __init__(self) -> None:
        self.exists = False
        self.loaded = False
        self.entities: list[dict[str, object]] = []
        self.load_calls = 0
        self.release_during_search = False

    def has_collection(self, collection_name: str) -> bool:
        return self.exists

    def drop_collection(self, collection_name: str) -> None:
        self.exists = False
        self.loaded = False
        self.entities.clear()

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        auto_id: bool,
        metric_type: str,
    ) -> None:
        self.exists = True

    def insert(self, collection_name: str, data: list[dict[str, object]]) -> object:
        self.entities.extend(data)
        return {}

    def load_collection(self, collection_name: str) -> None:
        self.loaded = True
        self.load_calls += 1

    def search(
        self,
        collection_name: str,
        data: list[list[float]],
        limit: int,
        output_fields: list[str],
        search_params: dict[str, object],
    ) -> list[list[dict[str, object]]]:
        if self.release_during_search:
            self.release_during_search = False
            self.loaded = False
            raise RuntimeError("collection was released; call load() before search")
        if not self.loaded:
            raise RuntimeError("call load() before search")
        return [[{"distance": 1.0, "entity": entity} for entity in self.entities[:limit]]]

    def close(self) -> None:
        return None


class BlockingMilvusClient(ReleasableMilvusClient):
    def __init__(self) -> None:
        super().__init__()
        self.block_search = False
        self.search_started = threading.Event()
        self.release_search = threading.Event()
        self._state_lock = threading.Lock()
        self.active_searches = 0
        self.max_active_searches = 0

    def search(
        self,
        collection_name: str,
        data: list[list[float]],
        limit: int,
        output_fields: list[str],
        search_params: dict[str, object],
    ) -> list[list[dict[str, object]]]:
        with self._state_lock:
            self.active_searches += 1
            self.max_active_searches = max(self.max_active_searches, self.active_searches)
        try:
            if self.block_search:
                self.search_started.set()
                assert self.release_search.wait(timeout=2)
                self.block_search = False
            return super().search(collection_name, data, limit, output_fields, search_params)
        finally:
            with self._state_lock:
                self.active_searches -= 1


def test_vector_chunking_respects_sentence_boundaries_and_overlap() -> None:
    sentence = "A short sentence about the river."
    text = " ".join([sentence] * 30)

    chunks = make_vector_chunks("story.md", text)

    assert len(chunks) == 2
    assert all(len(chunk.text) <= 800 for chunk in chunks)
    assert chunks[0].text.endswith("river.")
    assert chunks[1].text.startswith(sentence)
    assert chunks[0].text.endswith(chunks[1].text.split(sentence, 1)[0] + sentence)


def test_vector_chunking_bounds_oversized_content() -> None:
    chunks = make_vector_chunks("story.md", "word " * 500)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 800 for chunk in chunks)
    assert all(len(chunk.parent_text) <= VECTOR_PARENT_MAX_CHARACTERS for chunk in chunks)


def test_vector_chunking_preserves_pdf_pages_and_bounded_parents() -> None:
    text = "Page 2\n" + ("Reporting concerns protects everyone. " * 80)
    text += "\n\nPage 3\nSupplier standards apply globally."

    chunks = make_vector_chunks("policy.pdf", text)

    assert {chunk.page_label for chunk in chunks} == {"page 2", "page 3"}
    assert all(len(chunk.text) <= 800 for chunk in chunks)
    assert all(len(chunk.parent_text) <= VECTOR_PARENT_MAX_CHARACTERS for chunk in chunks)
    assert all(chunk.location.startswith("page ") for chunk in chunks)
    assert not any("Page 3" in chunk.text for chunk in chunks)
    page_two_parents = list(
        dict.fromkeys(chunk.parent_text for chunk in chunks if chunk.page_label == "page 2")
    )
    assert all(len(parent) >= VECTOR_PARENT_TARGET_CHARACTERS for parent in page_two_parents[:-1])


def test_hybrid_retrieval_recovers_lexical_and_dense_candidates() -> None:
    chunks = [
        VectorChunk(0, "semantic.md", "Boating and friendship beside the water."),
        VectorChunk(1, "lexical.md", "The exact quuxwidget specification is revision seven."),
        VectorChunk(2, "other.md", "A picnic was prepared indoors."),
    ]
    dense = [SearchResult("semantic.md", chunks[0].text, 0.95, 0)]

    results = hybrid_rank("quuxwidget near the river", chunks, dense, limit=2)

    assert {result.source for result in results} == {"semantic.md", "lexical.md"}
    assert [result.citation_id for result in results] == ["S1", "S2"]


def test_hybrid_retrieval_deduplicates_and_prefers_source_diversity() -> None:
    chunks = [
        VectorChunk(0, "one.md", "River bank travel details."),
        VectorChunk(1, "one.md", "River bank travel details."),
        VectorChunk(2, "one.md", "More river bank travel details and notes."),
        VectorChunk(3, "two.md", "River bank evidence from another account."),
    ]
    dense = [
        SearchResult(chunk.source, chunk.text, 1.0 - chunk.chunk_id / 10, chunk.chunk_id)
        for chunk in chunks
    ]

    results = hybrid_rank("river bank details", chunks, dense, limit=3)

    assert len({result.text for result in results}) == len(results)
    assert {result.source for result in results} == {"one.md", "two.md"}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Brief me about the company code of conduct", "broad"),
        ("Give me an overview of the employee handbook", "broad"),
        ("Explain the annual sustainability report", "broad"),
        ("What is the Speak Up process?", "targeted"),
        ("Tell me about the reporting procedure", "targeted"),
        ("Where can I report a concern?", "targeted"),
    ],
)
def test_query_mode_classification(query: str, expected: str) -> None:
    assert classify_query(query) == expected


def test_broad_retrieval_prefers_primary_and_covers_represented_policy_topics() -> None:
    topic_texts = [
        aliases[0] + " requirements and evidence." for aliases in POLICY_TOPIC_PATTERNS.values()
    ]
    chunks = [
        VectorChunk(
            index,
            "company-code-of-conduct.pdf",
            text,
            f"page {index + 1}",
            f"page {index + 1}",
            index,
            text,
        )
        for index, text in enumerate(topic_texts)
    ]
    chunks.append(
        VectorChunk(
            20,
            "unrelated-policy.pdf",
            "General policy overview.",
            "page 1",
            "page 1",
            20,
            "General policy overview.",
        )
    )
    dense = [SearchResult(chunk.source, chunk.text, 1.0, chunk.chunk_id) for chunk in chunks]

    results = broad_rank("Summarize the company code of conduct", chunks, dense)

    assert {result.source for result in results} == {"company-code-of-conduct.pdf"}
    assert set().union(*(set(result.topics) for result in results)) == set(POLICY_TOPIC_PATTERNS)
    assert len({result.location for result in results}) == len(results)


def test_broad_retrieval_covers_primary_sections_absent_from_query_candidates() -> None:
    chunks = [
        VectorChunk(
            0,
            "company-code-of-conduct.pdf",
            "Company code of conduct purpose and scope.",
            "page 1",
            "page 1",
            0,
            "Company code of conduct purpose and scope.",
        ),
        VectorChunk(
            1,
            "company-code-of-conduct.pdf",
            "Bribery, corruption, and financial crime are prohibited.",
            "page 8",
            "page 8",
            1,
            "Bribery, corruption, and financial crime are prohibited.",
        ),
        VectorChunk(
            2,
            "company-code-of-conduct.pdf",
            "Personal data must follow privacy and data protection requirements.",
            "page 12",
            "page 12",
            2,
            "Personal data must follow privacy and data protection requirements.",
        ),
    ]
    dense = [SearchResult(chunks[0].source, chunks[0].text, 1.0, chunks[0].chunk_id)]

    results = broad_rank("Summarize the company code of conduct", chunks, dense)

    assert {topic for result in results for topic in result.topics} >= {
        "purpose/scope/principles",
        "ethics/anti-bribery",
        "privacy/data",
    }
    assert {result.location for result in results} == {"page 1", "page 8", "page 12"}


def test_broad_retrieval_deduplicates_children_from_the_same_parent_location() -> None:
    parent = "Speak up reports are confidential and protected from retaliation."
    chunks = [
        VectorChunk(0, "policy.pdf", "Speak up reports.", "page 3", "page 3", 4, parent),
        VectorChunk(1, "policy.pdf", "Reports are confidential.", "page 3", "page 3", 4, parent),
    ]
    dense = [SearchResult(chunk.source, chunk.text, 1.0, chunk.chunk_id) for chunk in chunks]

    results = broad_rank("Summarize the policy", chunks, dense)

    assert len(results) == 1
    assert results[0].display_label == "policy.pdf — page 3"


def test_targeted_retrieval_remains_compact_child_evidence() -> None:
    child = "Focused reporting process."
    parent = child + " " + ("Broader background. " * 50)
    chunks = [VectorChunk(0, "policy.pdf", child, "page 4", "page 4", 0, parent)]

    results = hybrid_rank(
        "reporting process",
        chunks,
        [SearchResult("policy.pdf", child, 1.0, 0)],
        limit=1,
    )

    assert results[0].text == child
    assert results[0].location == "page 4, chunk 1"


def test_milvus_lite_indexes_searches_and_reuses_database(tmp_path: Path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "river.md").write_text("Rat and Mole travelled along the river bank.")
    (data_directory / "picnic.md").write_text("Badger prepared a picnic indoors.")
    database_path = tmp_path / "vectors.db"

    first = VectorKnowledgeBase(data_directory, database_path, DeterministicEmbedding())
    first_results = first.search("Who travelled by the river?")
    first.close()
    reopened_results = first.search("Who travelled by the river?")
    first.close()

    second = VectorKnowledgeBase(data_directory, database_path, DeterministicEmbedding())
    second_results = second.search("Tell me about the river")
    second.close()

    assert first.summary.chunk_count == 2
    assert first_results[0].source == "river.md"
    assert reopened_results[0].source == "river.md"
    assert second_results[0].source == "river.md"
    assert database_path.exists()
    assert database_path.with_suffix(".metadata.json").exists()
    metadata = json.loads(database_path.with_suffix(".metadata.json").read_text())
    assert metadata["chunking"] == "hierarchical-location-v2"
    assert metadata["retrieval"] == "hierarchical-rrf-coverage-v2"


def test_milvus_reuses_fingerprint_and_rebuilds_in_bounded_batches(tmp_path: Path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    for index in range(70):
        (data_directory / f"document-{index}.md").write_text(f"Evidence item {index}.")
    database_path = tmp_path / "vectors.db"

    initial_embedding = CountingEmbedding()
    initial = VectorKnowledgeBase(data_directory, database_path, initial_embedding)
    initial.search("evidence")
    initial.close()

    reused_embedding = CountingEmbedding()
    reused = VectorKnowledgeBase(data_directory, database_path, reused_embedding)
    reused.search("evidence")
    reused.close()

    (data_directory / "document-0.md").write_text("Changed evidence item.")
    changed_content_embedding = CountingEmbedding()
    changed_content = VectorKnowledgeBase(
        data_directory,
        database_path,
        changed_content_embedding,
    )
    changed_content.search("evidence")
    changed_content.close()

    changed_model_embedding = CountingEmbedding("counting-model-b")
    changed_model = VectorKnowledgeBase(data_directory, database_path, changed_model_embedding)
    changed_model.search("evidence")
    changed_model.close()

    assert initial_embedding.batch_sizes == [64, 6, 1]
    assert reused_embedding.batch_sizes == [1]
    assert changed_content_embedding.batch_sizes == [64, 6, 1]
    assert changed_model_embedding.batch_sizes == [64, 6, 1]


def test_milvus_schema_version_changes_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "policy.md").write_text("Policy purpose and scope.")
    database_path = tmp_path / "vectors.db"
    metadata_path = database_path.with_suffix(".metadata.json")

    original_embedding = CountingEmbedding()
    original = VectorKnowledgeBase(data_directory, database_path, original_embedding)
    original.search("policy")
    original.close()
    original_metadata = json.loads(metadata_path.read_text())
    monkeypatch.setattr(milvus, "MILVUS_SCHEMA_VERSION", "child-parent-location-v2")
    changed_embedding = CountingEmbedding()
    changed = VectorKnowledgeBase(data_directory, database_path, changed_embedding)
    changed.search("policy")
    changed.close()
    changed_metadata = json.loads(metadata_path.read_text())

    assert original_embedding.batch_sizes == [1, 1]
    assert changed_embedding.batch_sizes == [1, 1]
    assert changed_metadata["fingerprint"] != original_metadata["fingerprint"]
    assert changed_metadata["schema"] == "child-parent-location-v2"


def test_search_recovers_when_cached_collection_was_released(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "river.md").write_text("Evidence from the river.")
    client = ReleasableMilvusClient()

    def connect(database_path: Path) -> MilvusLiteClient:
        del database_path
        return cast(MilvusLiteClient, client)

    monkeypatch.setattr(milvus, "_connect", connect)
    knowledge = VectorKnowledgeBase(
        data_directory,
        tmp_path / "vectors.db",
        DeterministicEmbedding(),
    )

    assert knowledge.search("river")[0].source == "river.md"
    client.loaded = False
    assert knowledge.search("river")[0].source == "river.md"
    client.release_during_search = True
    assert knowledge.search("river")[0].source == "river.md"

    assert client.load_calls == 4


def test_milvus_rows_include_hierarchical_location_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "policy.txt").write_text("Page 7\nReporting concerns is confidential.")
    client = ReleasableMilvusClient()

    def connect(database_path: Path) -> MilvusLiteClient:
        del database_path
        return cast(MilvusLiteClient, client)

    monkeypatch.setattr(milvus, "_connect", connect)
    knowledge = VectorKnowledgeBase(data_directory, tmp_path / "vectors.db", CountingEmbedding())

    knowledge.search("reporting")

    assert client.entities[0]["page_label"] == "page 7"
    assert client.entities[0]["section"] == "page 7"
    assert client.entities[0]["parent_id"] == 0
    assert client.entities[0]["parent_text"] == "Reporting concerns is confidential."


def test_concurrent_searches_serialize_milvus_lifecycle_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "policy.txt").write_text("Reporting evidence.")
    client = BlockingMilvusClient()

    def connect(database_path: Path) -> MilvusLiteClient:
        del database_path
        return cast(MilvusLiteClient, client)

    monkeypatch.setattr(milvus, "_connect", connect)
    knowledge = VectorKnowledgeBase(data_directory, tmp_path / "vectors.db", CountingEmbedding())
    knowledge.search("reporting")
    client.block_search = True

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(knowledge.search, "reporting")
        assert client.search_started.wait(timeout=2)
        second = executor.submit(knowledge.search, "reporting")
        client.release_search.set()
        assert first.result()[0].source == "policy.txt"
        assert second.result()[0].source == "policy.txt"

    assert client.max_active_searches == 1
