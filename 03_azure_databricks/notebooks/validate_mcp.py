# Databricks notebook source
# ruff: noqa: F821
from __future__ import annotations

import logging
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient

from olympus_databricks.config import load_source_config
from olympus_databricks.logging import configure_logging, job_run, log_event

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("mcp_url", "")

environment = dict(os.environ)
environment["POLICY_MOGUL_MCP_URL"] = dbutils.widgets.get("mcp_url")
config = load_source_config(Path(dbutils.widgets.get("config_path")), environment)
configure_logging()
logger = logging.getLogger("olympus_databricks.mcp")

with job_run(logger, "validate_mcp", config.name):
    connection_name = config.options["connection"]
    connection = WorkspaceClient().connections.get(connection_name)
    if connection.name != connection_name:
        raise RuntimeError(f"Unity Catalog connection {connection_name!r} was not found")
    log_event(logger, "mcp_connection_validated", source=config.name, connection=connection_name)
