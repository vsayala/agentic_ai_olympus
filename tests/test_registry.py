from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from olympus_copilot_sdk.governance.registry import REQUIRED_ROOT_FILES, validate_registry


def _registry(tmp_path: Path, *, system_id: str = "example-system") -> Path:
    root = tmp_path / "ai_registry"
    for relative_path in REQUIRED_ROOT_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    (root / "evidence" / "external_evidence.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "evidence_id": "change-ticket",
                        "location": "approved-system://changes/123",
                        "owner": "Governance Owner",
                        "classification": "confidential",
                        "retention": "seven-years",
                        "sha256": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    system = root / "systems" / system_id
    system.mkdir(parents=True)
    artifacts = {
        name: f"systems/{system_id}/{name}.md"
        for name in (
            "model_card",
            "change_log",
            "privacy_assessment",
            "fundamental_rights_assessment",
        )
    }
    for relative_path in artifacts.values():
        (root / relative_path).write_text("reviewed\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "system_id": system_id,
        "name": "Example",
        "purpose": "Test registry validation.",
        "deployment_scope": "Synthetic test only.",
        "lifecycle": "pilot",
        "accountable_owner": "Product Owner",
        "technical_owner": "Engineering Owner",
        "components": [{"component_id": "router", "type": "software", "owner": "Thor"}],
        "model_providers": ["Example Provider"],
        "data_categories": ["synthetic"],
        "human_oversight": {
            "required": True,
            "mechanism": "Approval before release.",
            "escalation_owner": "Governance Owner",
        },
        "retention": {"schedule": "audit/retention_schedule.md", "owner": "Governance Owner"},
        "approvers": ["Human Governance Owner"],
        "external_evidence": ["change-ticket"],
        "regulatory": {
            "role": "deployer",
            "eu_ai_act_classification": "applicability-review-required",
            "risk_classification": "pending-human-approval",
            "classification_rationale": "Synthetic fixture.",
            "assessed_by": "Governance Owner",
            "assessed_on": "2026-08-11",
            "next_review_on": "2027-02-11",
        },
        "artifacts": artifacts,
    }
    (system / "manifest.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_complete_registry_passes(tmp_path: Path) -> None:
    assert validate_registry(_registry(tmp_path), as_of=date(2026, 8, 11)) == ("example-system",)


def test_system_directory_must_match_manifest_id(tmp_path: Path) -> None:
    root = _registry(tmp_path)
    manifest_path = root / "systems" / "example-system" / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["system_id"] = "different-system"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="System ID must match directory name"):
        validate_registry(root, as_of=date(2026, 8, 11))


def test_manifest_artifacts_must_exist(tmp_path: Path) -> None:
    root = _registry(tmp_path)
    (root / "systems" / "example-system" / "model_card.md").unlink()

    with pytest.raises(ValueError, match="Required registry artifact does not exist"):
        validate_registry(root, as_of=date(2026, 8, 11))


def test_stale_review_is_rejected(tmp_path: Path) -> None:
    root = _registry(tmp_path)

    with pytest.raises(ValueError, match="Registry review is stale"):
        validate_registry(root, as_of=date(2027, 2, 12))
