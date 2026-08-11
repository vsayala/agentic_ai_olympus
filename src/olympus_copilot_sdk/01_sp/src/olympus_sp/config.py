from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast


class RetrievalMode(StrEnum):
    FOUNDRY = "foundry"
    GRAPH = "graph"


@dataclass(frozen=True)
class SharePointConfig:
    tenant_id: str
    site_id: str
    library_id: str
    mode: RetrievalMode
    foundry_connection_id: str
    graph_endpoint: str


def load_config(path: Path) -> SharePointConfig:
    values = cast(dict[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    return SharePointConfig(
        tenant_id=_required(values, "tenant_id"),
        site_id=_required(values, "site_id"),
        library_id=_required(values, "library_id"),
        mode=RetrievalMode(_required(values, "mode")),
        foundry_connection_id=_required(values, "foundry_connection_id"),
        graph_endpoint=_required(values, "graph_endpoint"),
    )


def _required(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing configuration value: {key}")
    return value
