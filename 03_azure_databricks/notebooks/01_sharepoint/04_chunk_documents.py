# Databricks notebook source
# ruff: noqa: F821
import logging
from pathlib import Path

from olympus_databricks.sources.sharepoint import chunk_documents_step
from olympus_databricks.utilities import configure_logging, job_run, load_source_config
from olympus_databricks.utilities.sql import execute_step

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("connection", "")
dbutils.widgets.text("source_url", "")
environment = {
    "SHAREPOINT_CONNECTION": dbutils.widgets.get("connection"),
    "SHAREPOINT_SOURCE_URL": dbutils.widgets.get("source_url"),
}
config = load_source_config(Path(dbutils.widgets.get("config_path")), environment)
configure_logging()
with job_run(logging.getLogger(__name__), "chunk_documents", config.name):
    execute_step(spark, chunk_documents_step(config))
