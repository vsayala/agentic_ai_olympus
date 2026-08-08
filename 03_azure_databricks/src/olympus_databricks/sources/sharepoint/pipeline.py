# ruff: noqa: S608
from __future__ import annotations

from olympus_databricks.config import SourceConfig, validate_identifier
from olympus_databricks.utilities.sql import SqlStep


def land_files_step(config: SourceConfig) -> SqlStep:
    connection = validate_identifier("connection", _required_option(config, "connection"))
    source_url = _required_option(config, "source_url").replace("'", "''")
    return SqlStep(
        "land_raw_files",
        f"""CREATE OR REPLACE TABLE {config.namespace}.raw_files AS
SELECT path, modificationTime, length, content
FROM read_files(
  '{source_url}',
  databricks.connection => '{connection}',
  format => 'binaryFile',
  schemaEvolutionMode => 'none'
)""",
    )


def parse_documents_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "parse_documents",
        f"""CREATE OR REPLACE TABLE {config.namespace}.parsed_documents AS
SELECT path AS source_uri, modificationTime AS modified_at,
       ai_parse_document(content, map('version', '2.0')) AS parsed
FROM {config.namespace}.raw_files""",
    )


def chunk_documents_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "prepare_semantic_chunks",
        f"""CREATE OR REPLACE TABLE {config.namespace}.{config.semantic_table}
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
WITH prepared AS (
  SELECT source_uri, modified_at, ai_prep_search(parsed) AS result
  FROM {config.namespace}.parsed_documents
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
    )


def _required_option(config: SourceConfig, name: str) -> str:
    value = config.options.get(name)
    if not value:
        raise ValueError(f"Source {config.name!r} requires option {name!r}")
    return value
