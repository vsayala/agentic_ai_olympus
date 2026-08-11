from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from olympus_adb.strategy import RetrievalStrategy

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_PLACEHOLDER = re.compile(r"<[^>]+>|replace[_-]?me", re.IGNORECASE)


@dataclass(frozen=True)
class DatabricksConfig:
    catalog: str
    source_schema: str
    strategy: RetrievalStrategy
    vector_search_endpoint: str
    vector_search_index: str
    genie_space_id: str
    warehouse_id: str
    mcp_connection: str
    materialize_mcp: bool

    def __post_init__(self) -> None:
        if self.catalog != "data":
            raise ValueError("catalog must be data")
        if not _IDENTIFIER.fullmatch(self.source_schema):
            raise ValueError("source_schema must be a lowercase Unity Catalog identifier")
        if self.materialize_mcp:
            raise ValueError("external MCP materialization requires a separately approved design")
        if self.strategy is RetrievalStrategy.VECTOR_SEARCH:
            self._require_deployable("vector_search_endpoint", self.vector_search_endpoint)
            self._require_deployable("vector_search_index", self.vector_search_index)
            index_parts = self.vector_search_index.split(".")
            if index_parts[:2] != [self.catalog, self.source_schema] or len(index_parts) != 3:
                raise ValueError(
                    "vector_search_index must belong to the configured source namespace"
                )
            if not _IDENTIFIER.fullmatch(index_parts[2]):
                raise ValueError(
                    "vector_search_index name must be a lowercase Unity Catalog identifier"
                )
        elif self.strategy is RetrievalStrategy.GENIE:
            self._require_deployable("genie_space_id", self.genie_space_id)
            self._require_deployable("warehouse_id", self.warehouse_id)
        else:
            self._require_deployable("mcp_connection", self.mcp_connection)

    @property
    def namespace(self) -> str:
        return f"{self.catalog}.{self.source_schema}"

    @staticmethod
    def _require_deployable(key: str, value: str) -> None:
        if not value or _PLACEHOLDER.search(value):
            raise ValueError(f"{key} must be configured without placeholders")


def load_config(path: Path) -> DatabricksConfig:
    values = cast(dict[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    return DatabricksConfig(
        catalog=_string(values, "catalog"),
        source_schema=_string(values, "source_schema"),
        strategy=RetrievalStrategy(_string(values, "strategy")),
        vector_search_endpoint=_optional_string(values, "vector_search_endpoint"),
        vector_search_index=_optional_string(values, "vector_search_index"),
        genie_space_id=_optional_string(values, "genie_space_id"),
        warehouse_id=_optional_string(values, "warehouse_id"),
        mcp_connection=_optional_string(values, "mcp_connection"),
        materialize_mcp=_boolean(values, "materialize_mcp"),
    )


def _string(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing configuration value: {key}")
    return value


def _optional_string(values: dict[str, object], key: str) -> str:
    value = values.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"configuration value must be a string: {key}")
    return value


def _boolean(values: dict[str, object], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"missing boolean configuration value: {key}")
    return value
