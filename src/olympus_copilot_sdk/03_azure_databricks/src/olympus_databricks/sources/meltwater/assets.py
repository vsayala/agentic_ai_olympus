from __future__ import annotations

from typing import Protocol, cast

from databricks.sdk import WorkspaceClient


class ApiClientLike(Protocol):
    def do(self, method: str, path: str) -> object: ...


def validate_genie_space(workspace: WorkspaceClient, space_id: str) -> None:
    if not space_id or space_id.startswith("REPLACE_ME"):
        raise ValueError("A deployed Meltwater Genie space ID is required")
    api_client = cast(ApiClientLike, workspace.api_client)
    api_client.do("GET", f"/api/2.0/genie/spaces/{space_id}")
