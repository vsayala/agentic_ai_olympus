from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from olympus_adb.config import DatabricksConfig, load_config
from olympus_adb.contracts import AccessContext, RetrievalResult
from olympus_adb.retrieval import AccessDeniedError, DatabricksRetriever, SourceRow
from olympus_adb.strategy import RetrievalStrategy
from olympus_adb.tools import DatabricksEvidenceTool


class FakeBackend:
    def __init__(self, denied: bool = False) -> None:
        self.denied = denied
        self.operation = ""
        self.values: dict[str, object] = {}

    def query(self, **values: object) -> list[SourceRow]:
        return self._run("vector_search", values)

    def ask(self, **values: object) -> list[SourceRow]:
        return self._run("genie", values)

    def search(self, **values: object) -> list[SourceRow]:
        return self._run("mcp", values)

    def _run(self, operation: str, values: dict[str, object]) -> list[SourceRow]:
        self.operation = operation
        self.values = values
        if self.denied:
            raise AccessDeniedError("not authorized")
        return [SourceRow("record-1", "uc://data/source/record-1", "Answer", 0.8, {})]


def _config(strategy: RetrievalStrategy = RetrievalStrategy.VECTOR_SEARCH) -> DatabricksConfig:
    return DatabricksConfig(
        "data",
        "source_one",
        strategy,
        "endpoint",
        "data.source_one.index_one",
        "space-id",
        "warehouse-id",
        "connection-name",
        False,
    )


@pytest.mark.parametrize(
    ("strategy", "operation"),
    [
        (RetrievalStrategy.VECTOR_SEARCH, "vector_search"),
        (RetrievalStrategy.GENIE, "genie"),
        (RetrievalStrategy.MCP, "mcp"),
    ],
)
def test_strategy_selects_adapter_and_forwards_user_context(
    strategy: RetrievalStrategy, operation: str
) -> None:
    backend = FakeBackend()
    context = AccessContext("user-1", "user-token")
    retriever = DatabricksRetriever(_config(strategy), context, backend)

    result = DatabricksEvidenceTool(retriever).retrieve("question")

    assert backend.operation == operation
    assert backend.values["user_id"] == "user-1"
    assert backend.values["user_access_token"] == context.access_token
    assert result.evidence[0].source_id == "record-1"


def test_access_denied_returns_no_evidence() -> None:
    retriever = DatabricksRetriever(
        _config(), AccessContext("unauthorized", "token"), FakeBackend(denied=True)
    )
    assert retriever.search("restricted") == RetrievalResult((), True, "source_access_denied")


def test_catalog_and_source_schema_are_governed() -> None:
    assert _config().namespace == "data.source_one"
    with pytest.raises(ValueError, match="catalog must be data"):
        replace(_config(), catalog="other")
    with pytest.raises(ValueError, match="lowercase"):
        replace(_config(), source_schema="Bad-Schema")


def test_external_mcp_materialization_requires_separate_approval() -> None:
    with pytest.raises(ValueError, match="separately approved"):
        replace(_config(RetrievalStrategy.MCP), materialize_mcp=True)


@pytest.mark.parametrize(
    ("strategy", "field"),
    [
        (RetrievalStrategy.VECTOR_SEARCH, "vector_search_endpoint"),
        (RetrievalStrategy.VECTOR_SEARCH, "vector_search_index"),
        (RetrievalStrategy.GENIE, "genie_space_id"),
        (RetrievalStrategy.GENIE, "warehouse_id"),
        (RetrievalStrategy.MCP, "mcp_connection"),
    ],
)
@pytest.mark.parametrize("value", ["", "<replace-this>", "replace_me_value"])
def test_selected_strategy_rejects_missing_or_placeholder_fields(
    strategy: RetrievalStrategy, field: str, value: str
) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_config(strategy), **{field: value})


def test_vector_search_index_must_use_source_namespace() -> None:
    with pytest.raises(ValueError, match="configured source namespace"):
        replace(_config(), vector_search_index="data.other.index_one")
    with pytest.raises(ValueError, match="lowercase Unity Catalog identifier"):
        replace(_config(), vector_search_index="data.source_one.Bad-Index")


def test_load_config_allows_placeholders_only_for_unused_strategies(tmp_path: Path) -> None:
    config_path = tmp_path / "genie.toml"
    config_path.write_text(
        "\n".join(
            [
                'catalog = "data"',
                'source_schema = "source_one"',
                'strategy = "genie"',
                'vector_search_endpoint = "<vector-search-endpoint>"',
                'vector_search_index = "data.<source_schema>.<index-name>"',
                'genie_space_id = "space-id"',
                'warehouse_id = "warehouse-id"',
                'mcp_connection = "<governed-mcp-connection>"',
                "materialize_mcp = false",
            ]
        ),
        encoding="utf-8",
    )

    assert load_config(config_path).strategy is RetrievalStrategy.GENIE


def test_example_config_is_not_deployable() -> None:
    config_path = Path(__file__).parents[1] / "configs/example.toml"
    with pytest.raises(ValueError, match="vector_search_endpoint"):
        load_config(config_path)


def test_bundle_requires_an_explicit_source_schema() -> None:
    project_root = Path(__file__).parents[1]
    bundle = (project_root / "databricks.yml").read_text(encoding="utf-8")
    unity_catalog = (project_root / "resources/unity_catalog.yml").read_text(encoding="utf-8")

    assert "default: data" in bundle
    assert "default: replace_me_source" not in bundle
    assert "run_as_service_principal" not in bundle
    assert "prevent_destroy: true" in unity_catalog
    assert "name: ${var.source_schema}" in unity_catalog
    assert "catalog_name: ${resources.catalogs.data.name}" in unity_catalog


def test_deployment_workflow_promotes_project_with_manual_protected_deploy() -> None:
    workflow = (Path(__file__).parents[4] / ".github/workflows/databricks-deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "03_azure_databricks" not in workflow
    assert workflow.count("src/olympus_copilot_sdk/02_adb") == 4
    for command in (
        "uv sync --extra dev --locked",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run pyright",
        "uv run pytest",
        "uv run bandit -q -c pyproject.toml -r src",
        "uv run pip-audit",
        "uv build",
        "databricks bundle validate --target dev",
    ):
        assert command in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "environment: ${{ inputs.target }}" in workflow
    assert "DATABRICKS_AUTH_TYPE: github-oidc" in workflow
    assert "BUNDLE_VAR_source_schema: ${{ vars.DATABRICKS_SOURCE_SCHEMA }}" in workflow
    assert "DATABRICKS_BUNDLE_VAR" not in workflow
