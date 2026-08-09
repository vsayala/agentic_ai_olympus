from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

PROJECT_ROOT = Path(__file__).parents[1]


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = cast(object, loader.construct_object(key_node, deep=deep))  # pyright: ignore[reportUnknownMemberType]
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        value = cast(
            object,
            loader.construct_object(value_node, deep=deep),  # pyright: ignore[reportUnknownMemberType]
        )
        mapping[key] = value
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.load(path.read_text(), Loader=UniqueKeyLoader))  # noqa: S506


def test_all_bundle_yaml_is_valid() -> None:
    paths = [
        *PROJECT_ROOT.glob("*.yml"),
        *PROJECT_ROOT.joinpath("configs").rglob("*.yml"),
        *PROJECT_ROOT.joinpath("resources").rglob("*.yml"),
    ]

    assert paths
    assert all(_load(path) is not None for path in paths)


def test_bundle_has_promotion_targets_and_source_jobs() -> None:
    bundle = _load(PROJECT_ROOT / "databricks.yml")
    environments = _load(PROJECT_ROOT / "azure_databricks.yml")
    jobs = {
        path.stem.removesuffix(".job"): _load(path)
        for path in PROJECT_ROOT.joinpath("resources/jobs").glob("*.job.yml")
    }

    assert set(environments["targets"]) == {"dev", "qe", "stg", "prod"}
    assert set(jobs) == {"sharepoint", "meltwater", "policy_mogul"}
    assert all(document["resources"]["jobs"] for document in jobs.values())
    assert "policy_mogul_connection" in bundle["variables"]
    policy_job = jobs["policy_mogul"]["resources"]["jobs"]["policy_mogul_mcp_validation"]
    assert policy_job["tasks"][0]["notebook_task"]["base_parameters"]["connection"] == (
        "${var.policy_mogul_connection}"
    )


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
                assert notebook_path.read_text().startswith("# Databricks notebook source")
                config_path = notebook.get("base_parameters", {}).get("config_path")
                if config_path is not None:
                    prefix = "${workspace.file_path}/"
                    assert config_path.startswith(prefix)
                    assert (PROJECT_ROOT / config_path.removeprefix(prefix)).is_file()


def test_source_jobs_have_explicit_ordered_task_chains() -> None:
    expected_chains = {
        "sharepoint": [
            "validate_connection",
            "land_files",
            "parse_documents",
            "chunk_documents",
            "sync_ai_search",
            "validate_serving",
        ],
        "meltwater": [
            "land_raw_payloads",
            "bronze",
            "silver",
            "gold",
            "create_lookup_function",
            "validate_genie",
        ],
        "policy_mogul": ["validate_connection", "validate_serving"],
    }

    for source, expected in expected_chains.items():
        document = _load(PROJECT_ROOT / f"resources/jobs/{source}.job.yml")
        job = next(iter(document["resources"]["jobs"].values()))
        tasks = job["tasks"]
        assert [task["task_key"] for task in tasks] == expected
        for previous, task in zip(expected[:-1], tasks[1:], strict=True):
            assert task["depends_on"] == [{"task_key": previous}]


def test_every_notebook_task_installs_the_project_wheel() -> None:
    for job_path in PROJECT_ROOT.joinpath("resources/jobs").glob("*.job.yml"):
        document = _load(job_path)
        for job in document["resources"]["jobs"].values():
            environments = {
                item["environment_key"]: item["spec"]["dependencies"]
                for item in job.get("environments", [])
            }
            for task in job["tasks"]:
                libraries = [item.get("whl") for item in task.get("libraries", [])]
                environment = environments.get(task.get("environment_key"), [])
                assert "../../dist/*.whl" in libraries or "../../dist/*.whl" in environment
