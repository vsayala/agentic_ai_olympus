# Databricks notebook source
# ruff: noqa: F821
from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from olympus_databricks.api_ingestion import ApiPage, TransientApiError, ingest_api
from olympus_databricks.config import load_source_config
from olympus_databricks.logging import configure_logging, job_run, log_event


class HttpJsonTransport:
    def __init__(
        self,
        base_url: str,
        token: str,
        records_field: str,
        cursor_field: str,
    ) -> None:
        if urlsplit(base_url).scheme != "https":
            raise ValueError("API base_url must use HTTPS")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._records_field = records_field
        self._cursor_field = cursor_field

    def fetch(self, path: str, cursor: str | None) -> ApiPage:
        query = urlencode({"cursor": cursor}) if cursor else ""
        url = f"{self._base_url}{path}{'?' + query if query else ''}"
        request = Request(  # noqa: S310
            url,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310  # nosec B310
                body = json.loads(response.read())
        except HTTPError as error:
            if error.code == 429 or error.code >= 500:
                raise TransientApiError(f"API returned HTTP {error.code}") from error
            raise
        records = body.get(self._records_field, [])
        if not isinstance(records, list):
            raise ValueError(f"API field {self._records_field!r} must be a list")
        return ApiPage(records, body.get(self._cursor_field))


class DeltaRawWriter:
    def __init__(self, table: str, primary_key: str, source_uri: str) -> None:
        self._table = table
        self._primary_key = primary_key
        self._source_uri = source_uri

    def append(self, records: Sequence[Mapping[str, Any]]) -> None:
        ingested_at = datetime.now(UTC)
        rows = [
            (
                str(record[self._primary_key]),
                ingested_at,
                json.dumps(record, separators=(",", ":"), sort_keys=True),
                self._source_uri,
            )
            for record in records
        ]
        frame = spark.createDataFrame(
            rows,
            "event_id STRING, ingested_at TIMESTAMP, payload_json STRING, source_uri STRING",
        )
        frame.write.mode("append").saveAsTable(self._table)


dbutils.widgets.text("config_path", "")
config = load_source_config(Path(dbutils.widgets.get("config_path")), {})
token = dbutils.secrets.get(
    scope=config.options["secret_scope"],
    key=config.options["secret_key"],
)
transport = HttpJsonTransport(
    config.options["base_url"],
    token,
    config.options.get("records_field", "data"),
    config.options.get("cursor_field", "next_cursor"),
)
writer = DeltaRawWriter(
    f"{config.namespace}.raw_payloads",
    config.options["primary_key"],
    config.options["base_url"],
)

configure_logging()
logger = logging.getLogger("olympus_databricks.api")
with job_run(logger, "land_raw_payloads", config.name):
    count = ingest_api(transport, writer, config.options["api_path"])
    log_event(logger, "api_payloads_landed", source=config.name, record_count=count)
