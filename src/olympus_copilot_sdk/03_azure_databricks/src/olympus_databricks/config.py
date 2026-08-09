from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_ENVIRONMENT = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigurationError(ValueError):
    """Raised when a source configuration is incomplete or unsafe."""


@dataclass(frozen=True)
class SourceConfig:
    name: str
    kind: str
    catalog: str
    schema: str
    raw_volume: str
    checkpoint_volume: str
    semantic_table: str
    vector_index: str | None
    serving_endpoint: str
    options: dict[str, str]

    @property
    def namespace(self) -> str:
        return f"{self.catalog}.{self.schema}"


def load_source_config(path: Path, environment: dict[str, str] | None = None) -> SourceConfig:
    values = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    resolved = _resolve(values, environment or dict(os.environ))
    required = ("name", "kind", "catalog", "schema", "raw_volume", "checkpoint_volume")
    missing = [key for key in required if not resolved.get(key)]
    if missing:
        raise ConfigurationError(f"Missing required configuration: {', '.join(missing)}")
    for key in ("catalog", "schema", "raw_volume", "checkpoint_volume"):
        _validate_identifier(key, str(resolved[key]))
    name = str(resolved["name"])
    semantic_table = str(resolved.get("semantic_table", "semantic_chunks"))
    _validate_identifier("semantic_table", semantic_table)
    vector_index_value = resolved.get("vector_index")
    options = {str(key): str(value) for key, value in dict(resolved.get("options", {})).items()}
    return SourceConfig(
        name=name,
        kind=str(resolved["kind"]),
        catalog=str(resolved["catalog"]),
        schema=str(resolved["schema"]),
        raw_volume=str(resolved["raw_volume"]),
        checkpoint_volume=str(resolved["checkpoint_volume"]),
        semantic_table=semantic_table,
        vector_index=str(vector_index_value) if vector_index_value else None,
        serving_endpoint=str(resolved.get("serving_endpoint", f"{name}-hercules")),
        options=options,
    )


def _resolve(value: Any, environment: dict[str, str]) -> Any:
    if isinstance(value, dict):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _resolve(item, environment) for key, item in mapping.items()}
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_resolve(item, environment) for item in items]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in environment:
            raise ConfigurationError(f"Environment variable {key} is required")
        return environment[key]

    return _ENVIRONMENT.sub(replace, value)


def _validate_identifier(field: str, value: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ConfigurationError(f"{field} must be a Unity Catalog identifier, got {value!r}")


def validate_identifier(field: str, value: str) -> str:
    _validate_identifier(field, value)
    return value
