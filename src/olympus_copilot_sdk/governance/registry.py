from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "1.0"
LIFECYCLE_STATES = {"planned", "pilot", "active", "retired"}
REQUIRED_ROOT_FILES = (
    "REGISTRY_README.md",
    "OWNERS.md",
    "policies/acceptable_use.md",
    "policies/prohibited_uses.md",
    "policies/risk_appetite.md",
    "controls/dlp_rules.yaml",
    "controls/content_filters.yaml",
    "controls/human_review_gates.yaml",
    "evidence/external_evidence.json",
    "monitoring/drift_alerts.yaml",
    "monitoring/bias_dashboards.json",
    "monitoring/cost_per_decision.csv",
    "audit/retention_schedule.md",
    "vendors/README.md",
)
REQUIRED_ARTIFACTS = (
    "model_card",
    "change_log",
    "privacy_assessment",
    "fundamental_rights_assessment",
)


def load_structured_file(path: Path) -> Mapping[str, object]:
    try:
        value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON-compatible YAML in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    raw_mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw_mapping):
        raise ValueError(f"{path} must contain an object")
    return cast(dict[str, object], value)


def validate_registry(registry_root: Path, *, as_of: date | None = None) -> tuple[str, ...]:
    for relative_path in REQUIRED_ROOT_FILES:
        _require_file(registry_root, relative_path)
    systems_root = registry_root / "systems"
    if not systems_root.is_dir():
        raise ValueError("Registry must contain systems/")
    system_directories = sorted(path for path in systems_root.iterdir() if path.is_dir())
    if not system_directories:
        raise ValueError("Registry must contain at least one AI system")
    system_ids: list[str] = []
    for system_directory in system_directories:
        manifest = load_structured_file(system_directory / "manifest.yaml")
        system_id = _required_text(manifest, "system_id")
        if system_id != system_directory.name:
            raise ValueError(f"System ID must match directory name: {system_directory.name}")
        if system_id in system_ids:
            raise ValueError(f"Duplicate system ID: {system_id}")
        _validate_manifest(registry_root, manifest, as_of=as_of or date.today())
        system_ids.append(system_id)
    return tuple(system_ids)


def _validate_manifest(registry_root: Path, manifest: Mapping[str, object], *, as_of: date) -> None:
    if _required_text(manifest, "schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for key in (
        "name",
        "purpose",
        "deployment_scope",
        "accountable_owner",
        "technical_owner",
    ):
        _required_text(manifest, key)
    lifecycle = _required_text(manifest, "lifecycle")
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(f"Unsupported lifecycle: {lifecycle}")
    components = manifest.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("components must be a non-empty array")
    for component in cast(list[object], components):
        mapping = _mapping(component, "component")
        for key in ("component_id", "type", "owner"):
            _required_text(mapping, key)
    for key in ("model_providers", "data_categories", "approvers"):
        _required_text_array(manifest, key)
    oversight = _mapping(manifest.get("human_oversight"), "human_oversight")
    for key in ("required", "mechanism", "escalation_owner"):
        if key == "required":
            if not isinstance(oversight.get(key), bool):
                raise ValueError("human_oversight.required must be a boolean")
        else:
            _required_text(oversight, key)
    retention = _mapping(manifest.get("retention"), "retention")
    for key in ("schedule", "owner"):
        _required_text(retention, key)
    regulatory = _mapping(manifest.get("regulatory"), "regulatory")
    for key in (
        "role",
        "eu_ai_act_classification",
        "classification_rationale",
        "assessed_by",
    ):
        _required_text(regulatory, key)
    assessed_on = _required_date(regulatory, "assessed_on")
    next_review_on = _required_date(regulatory, "next_review_on")
    if next_review_on <= assessed_on:
        raise ValueError("next_review_on must be after assessed_on")
    if next_review_on < as_of:
        raise ValueError(f"Registry review is stale: {next_review_on.isoformat()}")
    _required_text(regulatory, "risk_classification")
    artifacts = _mapping(manifest.get("artifacts"), "artifacts")
    for key in REQUIRED_ARTIFACTS:
        _require_file(registry_root, _required_text(artifacts, key))
    evidence_ids = _required_text_array(manifest, "external_evidence")
    evidence = load_structured_file(registry_root / "evidence/external_evidence.json")
    records = evidence.get("records")
    if not isinstance(records, list):
        raise ValueError("external evidence records must be an array")
    known_ids = {_validate_evidence_record(record) for record in cast(list[object], records)}
    unknown_ids = set(evidence_ids) - known_ids
    if unknown_ids:
        raise ValueError(f"Unknown external evidence IDs: {', '.join(sorted(unknown_ids))}")


def _require_file(root: Path, relative_path: str) -> None:
    relative = Path(relative_path)
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts or not path.is_file():
        raise ValueError(f"Required registry artifact does not exist: {relative_path}")


def _required_text(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item.strip()


def _required_date(value: Mapping[str, object], key: str) -> date:
    text = _required_text(value, key)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{key} must be an ISO date") from error


def _required_text_array(value: Mapping[str, object], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list) or not items:
        raise ValueError(f"{key} must be a non-empty array")
    result: list[str] = []
    for item in cast(list[object], items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} entries must be non-empty strings")
        result.append(item.strip())
    return tuple(result)


def _validate_evidence_record(value: object) -> str:
    record = _mapping(value, "external evidence record")
    for key in ("evidence_id", "location", "owner", "classification", "retention"):
        _required_text(record, key)
    digest = record.get("sha256")
    if digest is not None and (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("sha256 must be null or a lowercase SHA-256 digest")
    return _required_text(record, "evidence_id")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    raw_mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw_mapping):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Olympus AI governance registry.")
    parser.add_argument("registry_root", nargs="?", type=Path, default=Path("ai_registry"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    options = parser.parse_args(arguments)
    system_ids = validate_registry(options.registry_root, as_of=options.as_of)
    print(f"AI REGISTRY PASS ({len(system_ids)} systems: {', '.join(system_ids)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
