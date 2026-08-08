from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from olympus_copilot_sdk.vector_db_02.chunking import make_vector_chunks
from olympus_copilot_sdk.vector_db_02.milvus import VectorKnowledgeBase


@dataclass(frozen=True)
class DeterministicEmbedding:
    dimension: int = 2
    model_name: str = "deterministic-test-embedding"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "river" in text.lower() else [0.0, 1.0] for text in texts]


def test_vector_chunking_has_stable_overlap() -> None:
    text = "a" * 900

    chunks = make_vector_chunks("story.md", text)

    assert len(chunks) == 2
    assert len(chunks[0].text) == 800
    assert chunks[0].text[-120:] == chunks[1].text[:120]


def test_milvus_lite_indexes_searches_and_reuses_database(tmp_path: Path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "river.md").write_text("Rat and Mole travelled along the river bank.")
    (data_directory / "picnic.md").write_text("Badger prepared a picnic indoors.")
    database_path = tmp_path / "vectors.db"

    first = VectorKnowledgeBase(data_directory, database_path, DeterministicEmbedding())
    first_results = first.search("Who travelled by the river?")
    first.close()

    second = VectorKnowledgeBase(data_directory, database_path, DeterministicEmbedding())
    second_results = second.search("Tell me about the river")
    second.close()

    assert first.summary.chunk_count == 2
    assert first_results[0].source == "river.md"
    assert second_results[0].source == "river.md"
    assert database_path.exists()
    assert database_path.with_suffix(".metadata.json").exists()
