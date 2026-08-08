# Databricks notebook source
# ruff: noqa: F821
import logging
from pathlib import Path

from olympus_databricks.sources.meltwater import bronze_step
from olympus_databricks.utilities import configure_logging, job_run, load_source_config
from olympus_databricks.utilities.sql import execute_step

dbutils.widgets.text("config_path", "")
config = load_source_config(Path(dbutils.widgets.get("config_path")), {})
configure_logging()
with job_run(logging.getLogger(__name__), "bronze", config.name):
    execute_step(spark, bronze_step(config))
