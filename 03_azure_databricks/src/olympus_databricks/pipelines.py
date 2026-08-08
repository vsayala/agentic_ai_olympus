# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass

from olympus_databricks.config import SourceConfig, validate_identifier
from olympus_databricks.contracts import SparkSessionLike

# All interpolated identifiers are validated and all literals are escaped before SQL generation.


@dataclass(frozen=True)
class SqlStep:
    name: str
    statement: str


def sharepoint_plan(config: SourceConfig) -> tuple[SqlStep, ...]:
    connection = validate_identifier("connection", _required_option(config, "connection"))
    source_url = _required_option(config, "source_url").replace("'", "''")
    namespace = config.namespace
    raw_table = f"{namespace}.raw_files"
    return (
        SqlStep(
            "land_raw_files",
            f"""CREATE OR REPLACE TABLE {raw_table} AS
SELECT path, modificationTime, length, content
FROM read_files(
  '{source_url}',
  databricks.connection => '{connection}',
  format => 'binaryFile',
  schemaEvolutionMode => 'none'
)""",
        ),
        SqlStep(
            "parse_documents",
            f"""CREATE OR REPLACE TABLE {namespace}.parsed_documents AS
SELECT path AS source_uri, modificationTime AS modified_at,
       ai_parse_document(content, map('version', '2.0')) AS parsed
FROM {raw_table}""",
        ),
        SqlStep(
            "prepare_semantic_chunks",
            f"""CREATE OR REPLACE TABLE {namespace}.{config.semantic_table}
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
WITH prepared AS (
  SELECT source_uri, modified_at, ai_prep_search(parsed) AS result
  FROM {namespace}.parsed_documents
)
SELECT chunk.value:chunk_id::STRING AS chunk_id,
       chunk.value:chunk_position::INT AS chunk_position,
       chunk.value:chunk_to_retrieve::STRING AS chunk_to_retrieve,
       chunk.value:chunk_to_embed::STRING AS chunk_to_embed,
       chunk.value:pages AS pages,
       source_uri,
       modified_at
FROM prepared,
LATERAL variant_explode(prepared.result:document.contents) AS chunk""",
        ),
    )


def api_medallion_plan(config: SourceConfig) -> tuple[SqlStep, ...]:
    namespace = config.namespace
    return (
        SqlStep(
            "bronze",
            f"""CREATE OR REPLACE TABLE {namespace}.bronze_events
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
SELECT event_id, ingested_at, parse_json(payload_json) AS payload, source_uri
FROM {namespace}.raw_payloads""",
        ),
        SqlStep(
            "silver",
            f"""CREATE OR REPLACE TABLE {namespace}.silver_events AS
SELECT event_id, ingested_at, source_uri, payload
FROM {namespace}.bronze_events WHERE payload IS NOT NULL""",
        ),
        SqlStep(
            "gold",
            f"""CREATE OR REPLACE TABLE {namespace}.gold_events AS
SELECT event_id, max(ingested_at) AS last_seen_at, any_value(source_uri) AS source_uri,
       any_value(payload) AS payload
FROM {namespace}.silver_events GROUP BY event_id""",
        ),
        SqlStep(
            "lookup_function",
            f"""CREATE OR REPLACE FUNCTION {namespace}.lookup_event(event_key STRING)
RETURNS TABLE (event_id STRING, last_seen_at TIMESTAMP, source_uri STRING, payload VARIANT)
COMMENT 'Deterministic event lookup for Hercules and Databricks agents'
RETURN SELECT event_id, last_seen_at, source_uri, payload
FROM {namespace}.gold_events WHERE event_id = event_key""",
        ),
    )


def execute_plan(spark: SparkSessionLike, steps: tuple[SqlStep, ...]) -> None:
    for step in steps:
        spark.sql(step.statement)


def _required_option(config: SourceConfig, name: str) -> str:
    value = config.options.get(name)
    if not value:
        raise ValueError(f"Source {config.name!r} requires option {name!r}")
    return value.replace("'", "''")
