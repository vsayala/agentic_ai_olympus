# ruff: noqa: S608
from __future__ import annotations

from olympus_databricks.config import SourceConfig
from olympus_databricks.utilities.sql import SqlStep


def bronze_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "bronze",
        f"""CREATE OR REPLACE TABLE {config.namespace}.bronze_events
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
SELECT event_id, ingested_at, parse_json(payload_json) AS payload, source_uri
FROM {config.namespace}.raw_payloads""",
    )


def silver_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "silver",
        f"""CREATE OR REPLACE TABLE {config.namespace}.silver_events AS
SELECT event_id, ingested_at, source_uri, payload
FROM {config.namespace}.bronze_events WHERE payload IS NOT NULL""",
    )


def gold_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "gold",
        f"""CREATE OR REPLACE TABLE {config.namespace}.gold_events AS
SELECT event_id, ingested_at AS last_seen_at, source_uri, payload
FROM {config.namespace}.silver_events
QUALIFY row_number() OVER (
    PARTITION BY event_id
    ORDER BY ingested_at DESC, source_uri DESC, to_json(payload) DESC
) = 1""",
    )


def lookup_function_step(config: SourceConfig) -> SqlStep:
    return SqlStep(
        "lookup_function",
        f"""CREATE OR REPLACE FUNCTION {config.namespace}.lookup_event(event_key STRING)
RETURNS TABLE (event_id STRING, last_seen_at TIMESTAMP, source_uri STRING, payload VARIANT)
COMMENT 'Deterministic event lookup for Hercules and Databricks agents'
RETURN SELECT event_id, last_seen_at, source_uri, payload
FROM {config.namespace}.gold_events WHERE event_id = event_key""",
    )
