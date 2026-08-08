from __future__ import annotations

from databricks.sdk import WorkspaceClient


def validate_connection(workspace: WorkspaceClient, connection_name: str) -> None:
    connection = workspace.connections.get(connection_name)
    if connection.name != connection_name:
        raise RuntimeError(f"Unity Catalog connection {connection_name!r} was not found")


def validate_serving_endpoint(workspace: WorkspaceClient, endpoint_name: str) -> None:
    endpoint = workspace.serving_endpoints.get(endpoint_name)
    if endpoint.name != endpoint_name:
        raise RuntimeError(f"Serving endpoint {endpoint_name!r} was not found")
