from __future__ import annotations

import argparse
import os
from pathlib import Path

from olympus_databricks.config import load_source_config
from olympus_databricks.strategy import retrieval_strategy


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an Olympus Databricks source config")
    parser.add_argument("config", type=Path)
    arguments = parser.parse_args()
    config = load_source_config(arguments.config, dict(os.environ))
    strategy = retrieval_strategy(config)
    print(f"{config.name}: {config.namespace} -> {strategy.value}")  # noqa: T201


if __name__ == "__main__":
    main()
