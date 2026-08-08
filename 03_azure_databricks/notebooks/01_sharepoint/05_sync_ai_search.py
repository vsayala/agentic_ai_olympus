# Databricks notebook source
# ruff: noqa: F821
import logging
from pathlib import Path

from databricks.sdk import WorkspaceClient

from olympus_databricks.sources.sharepoint.assets import sync_search_index
from olympus_databricks.utilities import configure_logging, job_run, load_source_config

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("connection", "")
dbutils.widgets.text("source_url", "")
dbutils.widgets.text("search_endpoint", "")
environment = {
    "SHAREPOINT_CONNECTION": dbutils.widgets.get("connection"),
    "SHAREPOINT_SOURCE_URL": dbutils.widgets.get("source_url"),
}
config = load_source_config(Path(dbutils.widgets.get("config_path")), environment)
configure_logging()
with job_run(logging.getLogger(__name__), "sync_ai_search", config.name):
    sync_search_index(WorkspaceClient(), config, dbutils.widgets.get("search_endpoint"))
