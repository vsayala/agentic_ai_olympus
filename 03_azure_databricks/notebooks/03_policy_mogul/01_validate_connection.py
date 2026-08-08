# Databricks notebook source
# ruff: noqa: F821
import logging
from pathlib import Path

from databricks.sdk import WorkspaceClient

from olympus_databricks.sources.policy_mogul import validate_connection
from olympus_databricks.utilities import configure_logging, job_run, load_source_config

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("mcp_url", "")
dbutils.widgets.text("connection", "")
environment = {
    "POLICY_MOGUL_MCP_URL": dbutils.widgets.get("mcp_url"),
    "POLICY_MOGUL_CONNECTION": dbutils.widgets.get("connection"),
}
config = load_source_config(Path(dbutils.widgets.get("config_path")), environment)
configure_logging()
with job_run(logging.getLogger(__name__), "validate_mcp_connection", config.name):
    validate_connection(WorkspaceClient(), config.options["connection"])
