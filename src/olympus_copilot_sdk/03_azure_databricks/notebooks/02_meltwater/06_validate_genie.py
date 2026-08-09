# Databricks notebook source
# ruff: noqa: F821
import logging

from databricks.sdk import WorkspaceClient

from olympus_databricks.sources.meltwater.assets import validate_genie_space
from olympus_databricks.utilities import configure_logging, job_run

dbutils.widgets.text("genie_space_id", "")
configure_logging()
with job_run(logging.getLogger(__name__), "validate_genie", "meltwater"):
    validate_genie_space(WorkspaceClient(), dbutils.widgets.get("genie_space_id"))
