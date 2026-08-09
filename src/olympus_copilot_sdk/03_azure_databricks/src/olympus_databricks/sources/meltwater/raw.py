from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol


class DataFrameWriterLike(Protocol):
    def mode(self, save_mode: str) -> DataFrameWriterLike: ...

    def saveAsTable(self, table: str) -> None: ...


class DataFrameLike(Protocol):
    @property
    def write(self) -> DataFrameWriterLike: ...


class SparkFrameSessionLike(Protocol):
    def createDataFrame(
        self,
        data: Sequence[tuple[str, datetime, str, str]],
        schema: str,
    ) -> DataFrameLike: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DeltaRawWriter:
    def __init__(
        self,
        spark: SparkFrameSessionLike,
        table: str,
        primary_key: str,
        source_uri: str,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._spark = spark
        self._table = table
        self._primary_key = primary_key
        self._source_uri = source_uri
        self._clock = clock

    def append(self, records: Sequence[Mapping[str, Any]]) -> None:
        ingested_at = self._clock()
        rows = [
            (
                str(record[self._primary_key]),
                ingested_at,
                json.dumps(record, separators=(",", ":"), sort_keys=True),
                self._source_uri,
            )
            for record in records
        ]
        frame = self._spark.createDataFrame(
            rows,
            "event_id STRING, ingested_at TIMESTAMP, payload_json STRING, source_uri STRING",
        )
        frame.write.mode("append").saveAsTable(self._table)
