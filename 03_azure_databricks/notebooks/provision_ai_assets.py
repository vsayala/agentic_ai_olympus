# Databricks notebook source
# ruff: noqa: F821
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

from olympus_databricks.config import load_source_config
from olympus_databricks.logging import configure_logging, job_run, log_event

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("search_endpoint", "")
dbutils.widgets.text("mode", "")

config = load_source_config(Path(dbutils.widgets.get("config_path")), {})
mode = dbutils.widgets.get("mode")
configure_logging()
logger = logging.getLogger("olympus_databricks.provision")

with job_run(logger, f"provision_{mode}", config.name):
    if mode == "ai_search":
        if config.vector_index is None:
            raise ValueError(f"Source {config.name} has no vector_index")
        workspace = WorkspaceClient()
        encoded_index = quote(config.vector_index, safe="")
        try:
            workspace.api_client.do("GET", f"/api/2.0/vector-search/indexes/{encoded_index}")
        except NotFound:
            workspace.api_client.do(
                "POST",
                "/api/2.0/vector-search/indexes",
                body={
                    "name": config.vector_index,
                    "endpoint_name": dbutils.widgets.get("search_endpoint"),
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
        workspace.api_client.do(
            "POST",
            f"/api/2.0/vector-search/indexes/{encoded_index}/sync",
        )
        log_event(logger, "ai_search_sync_requested", index=config.vector_index)
    else:
        raise ValueError(f"Unsupported provisioning mode: {mode}")
