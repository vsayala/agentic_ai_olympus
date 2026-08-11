from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from olympus_copilot_sdk.channel.config import (
    ChannelExposureConfig,
    EvidenceClassification,
    load_channel_config,
)

ROOT = Path(__file__).parents[1]
EXAMPLE_CONFIG = ROOT / "src" / "olympus_copilot_sdk" / "channel" / "example_channel_config.json"


def _config() -> dict[str, object]:
    return cast(dict[str, object], json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8")))


def test_placeholder_static_config_is_valid() -> None:
    config = load_channel_config(EXAMPLE_CONFIG)

    assert config.evidence_classification is EvidenceClassification.STATIC
    assert config.expected_channels == ("teams", "microsoft_365_copilot")
    assert config.ownership.retrieval_authorization == "loki"
    assert config.ownership.agent_tool_semantics == "thor"


@pytest.mark.parametrize("field", ["expected_channels", "expected_scopes"])
def test_missing_channels_or_scopes_are_rejected(field: str) -> None:
    payload = _config()
    payload[field] = []

    with pytest.raises(ValueError, match=field):
        ChannelExposureConfig.from_mapping(payload)


@pytest.mark.parametrize(
    ("section", "field"),
    [("foundry", "project_endpoint"), ("sharepoint_test", "site_url")],
)
def test_http_endpoints_are_rejected(section: str, field: str) -> None:
    payload = _config()
    nested = cast(dict[str, object], payload[section])
    nested[field] = "http://unsafe.example.test"

    with pytest.raises(ValueError, match="must be an HTTPS URL"):
        ChannelExposureConfig.from_mapping(payload)


def test_same_authorized_and_denied_principal_is_rejected() -> None:
    payload = _config()
    sharepoint = cast(dict[str, object], payload["sharepoint_test"])
    sharepoint["denied_principal_label"] = sharepoint["authorized_principal_label"]

    with pytest.raises(ValueError, match="must be different"):
        ChannelExposureConfig.from_mapping(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("access_token", "replace_me_token"), ("diagnostic", "Bearer exposed-value")],
)
def test_secrets_and_tokens_are_rejected(field: str, value: str) -> None:
    payload = _config()
    payload[field] = value

    with pytest.raises(ValueError, match="Secrets or tokens are not allowed"):
        ChannelExposureConfig.from_mapping(payload)


def test_authenticated_config_rejects_unresolved_placeholders() -> None:
    payload = deepcopy(_config())
    payload["evidence_classification"] = "AUTHENTICATED"

    with pytest.raises(ValueError, match="cannot contain unresolved"):
        ChannelExposureConfig.from_mapping(payload)


def test_example_artifact_filenames_and_json_are_lowercase_and_parseable() -> None:
    artifacts = sorted(EXAMPLE_CONFIG.parent.glob("*.json"))

    assert artifacts
    assert all(path.name == path.name.lower() for path in artifacts)
    assert all(isinstance(json.loads(path.read_text(encoding="utf-8")), dict) for path in artifacts)
