# Databricks notebook source
# ruff: noqa: F821
import logging

from databricks.sdk import WorkspaceClient

from olympus_databricks.sources.sharepoint.assets import validate_connection
from olympus_databricks.utilities import configure_logging, job_run, log_event

dbutils.widgets.text("connection", "")
connection = dbutils.widgets.get("connection")
configure_logging()
logger = logging.getLogger(__name__)
with job_run(logger, "validate_connection", "sharepoint"):
    validate_connection(WorkspaceClient(), connection)
    log_event(logger, "connection_validated", source="sharepoint")
