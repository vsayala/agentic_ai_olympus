from __future__ import annotations

import logging
from pathlib import Path

import pytest

from olympus_databricks.api_ingestion import (
    ApiIngestionError,
    ApiPage,
    TransientApiError,
    ingest_api,
)
from olympus_databricks.config import ConfigurationError, SourceConfig, load_source_config
from olympus_databricks.contracts import Evidence
from olympus_databricks.hercules import HerculesDatabricksTool
from olympus_databricks.logging import job_run
from olympus_databricks.pipelines import api_medallion_plan, execute_plan, sharepoint_plan
from olympus_databricks.retrieval import AISearchRetriever
from olympus_databricks.strategy import RetrievalStrategy, retrieval_strategy


class FakeSpark:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, query: str) -> object:
        self.statements.append(query)
        return object()


class FakeRetriever:
    def search(self, query: str, limit: int = 8) -> list[Evidence]:
        return [Evidence("old", "policy.pdf", query, 0.9, {})][:limit]


class FakeIndex:
    def similarity_search(self, **kwargs: object) -> dict[str, object]:
        assert kwargs["query_type"] == "HYBRID"
        return {
            "manifest": {
                "columns": [
                    {"name": "chunk_id"},
                    {"name": "chunk_to_retrieve"},
                    {"name": "source_uri"},
                    {"name": "score"},
                ]
            },
            "result": {"data_array": [["c1", "Evidence", "policy.pdf", 0.8]]},
        }


class FakeApiTransport:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, path: str, cursor: str | None) -> ApiPage:
        assert path == "/events"
        self.calls += 1
        if self.calls == 1:
            raise TransientApiError("busy")
        if cursor is None:
            return ApiPage([{"id": "1"}], "next")
        return ApiPage([{"id": "2"}])


class FakeRawWriter:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def append(self, records: object) -> None:
        self.ids.extend(str(record["id"]) for record in records)  # type: ignore[index, union-attr]


def _config(kind: str = "files") -> SourceConfig:
    return SourceConfig(
        "sharepoint",
        kind,
        "data",
        "sharepoint",
        "raw",
        "checkpoints",
        "semantic_chunks",
        "data.sharepoint.semantic_index",
        "sharepoint-hercules",
        {"connection": "sharepoint_connection", "source_url": "https://example.test/docs"},
    )


def test_config_resolves_environment_and_rejects_unsafe_identifiers(tmp_path: Path) -> None:
    path = tmp_path / "source.yml"
    path.write_text(
        "name: sharepoint\nkind: files\ncatalog: ${CATALOG}\nschema: sharepoint\n"
        "raw_volume: raw\ncheckpoint_volume: checkpoints\n",
        encoding="utf-8",
    )
    assert load_source_config(path, {"CATALOG": "data"}).namespace == "data.sharepoint"
    path.write_text(path.read_text().replace("sharepoint\nraw", "bad-name\nraw"))
    with pytest.raises(ConfigurationError, match="Unity Catalog identifier"):
        load_source_config(path, {"CATALOG": "data"})


def test_sharepoint_plan_uses_versioned_ai_functions_and_change_feed() -> None:
    steps = sharepoint_plan(_config())
    sql = "\n".join(step.statement for step in steps)
    assert [step.name for step in steps] == [
        "land_raw_files",
        "parse_documents",
        "prepare_semantic_chunks",
    ]
    assert "ai_parse_document(content, map('version', '2.0'))" in sql
    assert "ai_prep_search(parsed)" in sql
    assert "delta.enableChangeDataFeed = true" in sql


def test_api_plan_executes_bronze_silver_gold_in_order() -> None:
    spark = FakeSpark()
    execute_plan(spark, api_medallion_plan(_config("api")))
    assert len(spark.statements) == 4
    assert "bronze_events" in spark.statements[0]
    assert "silver_events" in spark.statements[1]
    assert "gold_events" in spark.statements[2]
    assert "lookup_event" in spark.statements[3]


def test_job_run_logs_context_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError, match="failed"):
        with job_run(logging.getLogger("test"), "semantic", "sharepoint"):
            raise RuntimeError("failed")
    assert "job_failed" in caplog.text
    assert "sharepoint" in caplog.text


def test_hercules_tool_reassigns_stable_citation_ids() -> None:
    evidence = HerculesDatabricksTool(FakeRetriever()).retrieve("policy")
    assert evidence[0].citation_id == "S1"
    assert evidence[0].source == "policy.pdf"


def test_ai_search_retriever_normalizes_sdk_response() -> None:
    evidence = AISearchRetriever(FakeIndex()).search("policy")
    assert evidence == [
        Evidence(
            "",
            "policy.pdf",
            "Evidence",
            0.8,
            {"chunk_id": "c1", "source_uri": "policy.pdf"},
        )
    ]


def test_api_ingestion_retries_and_writes_each_page() -> None:
    transport = FakeApiTransport()
    writer = FakeRawWriter()
    waits: list[float] = []

    count = ingest_api(transport, writer, "/events", wait=waits.append)

    assert count == 2
    assert writer.ids == ["1", "2"]
    assert waits == [1.0]


def test_api_ingestion_rejects_repeated_cursor() -> None:
    class RepeatingTransport:
        def fetch(self, path: str, cursor: str | None) -> ApiPage:
            return ApiPage([], "same")

    with pytest.raises(ApiIngestionError, match="cursor repeated"):
        ingest_api(RepeatingTransport(), FakeRawWriter(), "/events")


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("files", RetrievalStrategy.AI_SEARCH),
        ("api", RetrievalStrategy.GENIE),
        ("mcp", RetrievalStrategy.EXTERNAL_MCP),
    ],
)
def test_retrieval_strategy_matches_source_shape(
    kind: str,
    expected: RetrievalStrategy,
) -> None:
    assert retrieval_strategy(_config(kind)) is expected
