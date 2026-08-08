# Databricks notebook source
# ruff: noqa: F821
from __future__ import annotations

import logging
from pathlib import Path

from olympus_databricks.config import load_source_config
from olympus_databricks.logging import configure_logging, job_run
from olympus_databricks.pipelines import api_medallion_plan, execute_plan, sharepoint_plan

dbutils.widgets.text("config_path", "")
dbutils.widgets.text("pipeline", "")
dbutils.widgets.text("connection", "")
dbutils.widgets.text("source_url", "")

config_path = Path(dbutils.widgets.get("config_path"))
environment = {
    "SHAREPOINT_CONNECTION": dbutils.widgets.get("connection"),
    "SHAREPOINT_SOURCE_URL": dbutils.widgets.get("source_url"),
}
config = load_source_config(config_path, environment)
pipeline = dbutils.widgets.get("pipeline")
steps = sharepoint_plan(config) if pipeline == "sharepoint" else api_medallion_plan(config)

configure_logging()
logger = logging.getLogger("olympus_databricks.pipeline")
with job_run(logger, pipeline, config.name):
    execute_plan(spark, steps)
