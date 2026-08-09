# Databricks notebook source
# ruff: noqa: F821
import logging
from pathlib import Path

from olympus_databricks.api_ingestion import ingest_api
from olympus_databricks.sources.meltwater import DeltaRawWriter
from olympus_databricks.utilities import configure_logging, job_run, load_source_config, log_event
from olympus_databricks.utilities.http import HttpJsonTransport

dbutils.widgets.text("config_path", "")
config = load_source_config(Path(dbutils.widgets.get("config_path")), {})
token = dbutils.secrets.get(
    scope=config.options["secret_scope"],
    key=config.options["secret_key"],
)
transport = HttpJsonTransport(
    config.options["base_url"],
    token,
    config.options.get("records_field", "data"),
    config.options.get("cursor_field", "next_cursor"),
)
writer = DeltaRawWriter(
    spark,
    f"{config.namespace}.raw_payloads",
    config.options["primary_key"],
    config.options["base_url"],
)
configure_logging()
logger = logging.getLogger(__name__)
with job_run(logger, "land_raw_payloads", config.name):
    count = ingest_api(transport, writer, config.options["api_path"])
    log_event(logger, "api_payloads_landed", source=config.name, record_count=count)
