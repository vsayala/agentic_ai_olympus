from __future__ import annotations

from dataclasses import dataclass

from olympus_databricks.contracts import SparkSessionLike


@dataclass(frozen=True)
class SqlStep:
    name: str
    statement: str


def execute_step(spark: SparkSessionLike, step: SqlStep) -> None:
    spark.sql(step.statement)


def execute_plan(spark: SparkSessionLike, steps: tuple[SqlStep, ...]) -> None:
    for step in steps:
        execute_step(spark, step)
