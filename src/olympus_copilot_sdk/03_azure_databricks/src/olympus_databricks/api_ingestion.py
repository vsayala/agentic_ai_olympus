from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import sleep
from typing import Any, Protocol


class TransientApiError(RuntimeError):
    """Raised when an API operation is safe to retry."""


class ApiIngestionError(RuntimeError):
    """Raised when pagination cannot complete safely."""


@dataclass(frozen=True)
class ApiPage:
    records: Sequence[Mapping[str, Any]]
    next_cursor: str | None = None


class ApiTransport(Protocol):
    def fetch(self, path: str, cursor: str | None) -> ApiPage: ...


class RawPayloadWriter(Protocol):
    def append(self, records: Sequence[Mapping[str, Any]]) -> None: ...


def ingest_api(
    transport: ApiTransport,
    writer: RawPayloadWriter,
    path: str,
    *,
    max_pages: int = 1000,
    retries: int = 3,
    retry_delay_seconds: float = 1.0,
    wait: Callable[[float], None] = sleep,
) -> int:
    if max_pages < 1 or retries < 0:
        raise ValueError("max_pages must be positive and retries cannot be negative")

    cursor: str | None = None
    seen_cursors: set[str] = set()
    total = 0
    for _ in range(max_pages):
        page = _fetch_with_retry(
            transport,
            path,
            cursor,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            wait=wait,
        )
        if page.records:
            writer.append(page.records)
            total += len(page.records)
        cursor = page.next_cursor
        if cursor is None:
            return total
        if cursor in seen_cursors:
            raise ApiIngestionError(f"API pagination cursor repeated: {cursor!r}")
        seen_cursors.add(cursor)
    raise ApiIngestionError(f"API pagination exceeded max_pages={max_pages}")


def _fetch_with_retry(
    transport: ApiTransport,
    path: str,
    cursor: str | None,
    *,
    retries: int,
    retry_delay_seconds: float,
    wait: Callable[[float], None],
) -> ApiPage:
    for attempt in range(retries + 1):
        try:
            return transport.fetch(path, cursor)
        except TransientApiError:
            if attempt == retries:
                raise
            wait(retry_delay_seconds * (2**attempt))
    raise AssertionError("retry loop must return or raise")
