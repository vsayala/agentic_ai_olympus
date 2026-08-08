from __future__ import annotations

from typing import Protocol, cast
from urllib.parse import quote

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

from olympus_databricks.config import SourceConfig


class ApiClientLike(Protocol):
    def do(self, method: str, path: str, *, body: dict[str, object] | None = None) -> object: ...


def validate_connection(workspace: WorkspaceClient, connection_name: str) -> None:
    connection = workspace.connections.get(connection_name)
    if connection.name != connection_name:
        raise RuntimeError(f"Unity Catalog connection {connection_name!r} was not found")


def sync_search_index(
    workspace: WorkspaceClient,
    config: SourceConfig,
    endpoint_name: str,
) -> None:
    if config.vector_index is None:
        raise ValueError(f"Source {config.name!r} has no vector_index")
    api_client = cast(ApiClientLike, workspace.api_client)
    encoded_index = quote(config.vector_index, safe="")
    try:
        api_client.do("GET", f"/api/2.0/vector-search/indexes/{encoded_index}")
    except NotFound:
        api_client.do(
            "POST",
            "/api/2.0/vector-search/indexes",
            body={
                "name": config.vector_index,
                "endpoint_name": endpoint_name,
                "primary_key": "chunk_id",
                "index_type": "DELTA_SYNC",
                "delta_sync_index_spec": {
                    "source_table": f"{config.namespace}.{config.semantic_table}",
                    "pipeline_type": config.options.get("sync_mode", "TRIGGERED"),
                    "embedding_source_columns": [
                        {
                            "name": "chunk_to_embed",
                            "embedding_model_endpoint_name": "databricks-qwen3-embedding-0-6b",
                        }
                    ],
                    "columns_to_sync": [
                        "chunk_to_retrieve",
                        "source_uri",
                        "pages",
                        "modified_at",
                    ],
                },
            },
        )
    api_client.do("POST", f"/api/2.0/vector-search/indexes/{encoded_index}/sync")


def validate_serving_endpoint(workspace: WorkspaceClient, endpoint_name: str) -> None:
    endpoint = workspace.serving_endpoints.get(endpoint_name)
    if endpoint.name != endpoint_name:
        raise RuntimeError(f"Serving endpoint {endpoint_name!r} was not found")
