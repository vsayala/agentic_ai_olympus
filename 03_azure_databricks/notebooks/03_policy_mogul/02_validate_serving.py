# Databricks notebook source
# ruff: noqa: F821
import logging

from databricks.sdk import WorkspaceClient

from olympus_databricks.sources.policy_mogul import validate_serving_endpoint
from olympus_databricks.utilities import configure_logging, job_run

dbutils.widgets.text("serving_endpoint", "")
configure_logging()
with job_run(logging.getLogger(__name__), "validate_serving", "policy_mogul"):
    validate_serving_endpoint(WorkspaceClient(), dbutils.widgets.get("serving_endpoint"))
