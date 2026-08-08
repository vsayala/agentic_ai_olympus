from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

PROJECT_ROOT = Path(__file__).parents[1]


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def test_all_bundle_yaml_is_valid() -> None:
    paths = [
        *PROJECT_ROOT.glob("*.yml"),
        *PROJECT_ROOT.joinpath("configs").rglob("*.yml"),
        *PROJECT_ROOT.joinpath("resources").rglob("*.yml"),
    ]

    assert paths
    assert all(_load(path) is not None for path in paths)


def test_bundle_has_promotion_targets_and_source_jobs() -> None:
    environments = _load(PROJECT_ROOT / "azure_databricks.yml")
    jobs = {
        path.stem.removesuffix(".job"): _load(path)
        for path in PROJECT_ROOT.joinpath("resources/jobs").glob("*.job.yml")
    }

    assert set(environments["targets"]) == {"dev", "qe", "stg", "prod"}
    assert set(jobs) == {"sharepoint", "meltwater", "policy_mogul"}
    assert all(document["resources"]["jobs"] for document in jobs.values())


def test_job_paths_resolve_to_bundle_files() -> None:
    for job_path in PROJECT_ROOT.joinpath("resources/jobs").glob("*.job.yml"):
        document = _load(job_path)
        jobs = document["resources"]["jobs"].values()
        for job in jobs:
            for task in job["tasks"]:
                notebook = task.get("notebook_task")
                if notebook is None:
                    continue
                notebook_path = (job_path.parent / notebook["notebook_path"]).resolve()
                assert notebook_path.is_file()
                config_path = notebook.get("base_parameters", {}).get("config_path")
                if config_path is not None:
                    prefix = "${workspace.file_path}/"
                    assert config_path.startswith(prefix)
                    assert (PROJECT_ROOT / config_path.removeprefix(prefix)).is_file()
