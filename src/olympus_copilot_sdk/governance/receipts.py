from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Self, cast

CONTRACT_VERSION = "1.0"
MAX_CHALLENGE_ROUND = 2


class ReviewStatus(StrEnum):
    PASS = "PASS"  # nosec B105  # noqa: S105 - governance status
    CONDITIONAL_PASS = "CONDITIONAL PASS"  # nosec B105  # noqa: S105
    BLOCKED = "BLOCKED"


class Specialist(StrEnum):
    LOKI = "loki"
    THOR = "thor"
    HELA = "hela"


@dataclass(frozen=True)
class CheckResult:
    command: str
    outcome: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        command = _required_text(value, "command")
        outcome = _required_text(value, "outcome")
        if outcome not in {"PASS", "FAIL", "SKIPPED"}:
            raise ValueError(f"Unsupported check outcome: {outcome}")
        return cls(command, outcome)


@dataclass(frozen=True)
class Evidence:
    reference: str
    claim: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        return cls(_required_text(value, "reference"), _required_text(value, "claim"))


@dataclass(frozen=True)
class ReviewReceipt:
    contract_version: str
    task_id: str
    revision: str
    specialist: Specialist
    scope: tuple[str, ...]
    status: ReviewStatus
    findings: tuple[str, ...]
    conditions: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    checks: tuple[CheckResult, ...]
    artifact_hash: str
    reviewed_at: datetime
    challenge_round: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        if _required_text(value, "contract_version") != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        status = ReviewStatus(_required_text(value, "status"))
        conditions = _text_tuple(value, "conditions")
        if status is ReviewStatus.PASS and conditions:
            raise ValueError("PASS receipts cannot contain unresolved conditions")
        if status is not ReviewStatus.PASS and not conditions:
            raise ValueError(f"{status.value} receipts must contain at least one condition")
        challenge_round = value.get("challenge_round")
        if not isinstance(challenge_round, int) or not 0 <= challenge_round <= MAX_CHALLENGE_ROUND:
            raise ValueError(f"challenge_round must be between 0 and {MAX_CHALLENGE_ROUND}")
        artifact_hash = _required_text(value, "artifact_hash")
        invalid_character = any(character not in "0123456789abcdef" for character in artifact_hash)
        if len(artifact_hash) != 64 or invalid_character:
            raise ValueError("artifact_hash must be a lowercase SHA-256 digest")
        reviewed_at_text = _required_text(value, "reviewed_at").replace("Z", "+00:00")
        reviewed_at = datetime.fromisoformat(reviewed_at_text)
        if reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must include a timezone")
        evidence = tuple(
            Evidence.from_mapping(item) for item in _mapping_sequence(value, "evidence")
        )
        if not evidence:
            raise ValueError("evidence must contain at least one claim")
        return cls(
            contract_version=CONTRACT_VERSION,
            task_id=_required_text(value, "task_id"),
            revision=_required_text(value, "revision"),
            specialist=Specialist(_required_text(value, "specialist")),
            scope=_text_tuple(value, "scope", required=True),
            status=status,
            findings=_text_tuple(value, "findings"),
            conditions=conditions,
            evidence=evidence,
            checks=tuple(
                CheckResult.from_mapping(item) for item in _mapping_sequence(value, "checks")
            ),
            artifact_hash=artifact_hash,
            reviewed_at=reviewed_at.astimezone(UTC),
            challenge_round=challenge_round,
        )


def calculate_artifact_hash(root: Path, paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(set(paths)):
        path = root / relative_path
        if not path.is_file():
            raise ValueError(f"Reviewed artifact does not exist: {relative_path}")
        digest.update(relative_path.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_receipts(path: Path) -> tuple[ReviewReceipt, ...]:
    payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(payload, list):
        raise ValueError("Receipt file must contain a JSON array")
    items = cast(list[object], payload)
    return tuple(ReviewReceipt.from_mapping(_as_mapping(item, "receipt")) for item in items)


def validate_review_set(
    receipts: Sequence[ReviewReceipt],
    *,
    task_id: str,
    revision: str,
    root: Path | None = None,
) -> None:
    by_specialist: dict[Specialist, ReviewReceipt] = {}
    for receipt in receipts:
        if receipt.specialist in by_specialist:
            raise ValueError(f"Duplicate receipt for {receipt.specialist.value}")
        by_specialist[receipt.specialist] = receipt
        if receipt.task_id != task_id:
            raise ValueError(f"Receipt task mismatch for {receipt.specialist.value}")
        if receipt.revision != revision:
            raise ValueError(f"Stale revision for {receipt.specialist.value}")
        current_hash = calculate_artifact_hash(root, receipt.scope) if root is not None else None
        if current_hash is not None and current_hash != receipt.artifact_hash:
            raise ValueError(f"Stale artifact hash for {receipt.specialist.value}")
    missing = set(Specialist) - set(by_specialist)
    if missing:
        names = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"Missing specialist receipts: {names}")


def aggregate_odin_status(receipts: Sequence[ReviewReceipt]) -> str:
    statuses = {receipt.status for receipt in receipts}
    if ReviewStatus.BLOCKED in statuses or len(receipts) != len(Specialist):
        return "ODIN BLOCKED"
    if ReviewStatus.CONDITIONAL_PASS in statuses:
        return "ODIN CONDITIONAL PASS"
    return "ODIN PASS"


def _required_text(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item.strip()


def _text_tuple(
    value: Mapping[str, object], key: str, *, required: bool = False
) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise ValueError(f"{key} must be an array of non-empty strings")
    values = cast(list[object], items)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{key} must be an array of non-empty strings")
    if required and not values:
        raise ValueError(f"{key} must not be empty")
    return tuple(cast(str, item).strip() for item in values)


def _mapping_sequence(value: Mapping[str, object], key: str) -> tuple[Mapping[str, object], ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise ValueError(f"{key} must be an array")
    return tuple(_as_mapping(item, key) for item in cast(list[object], items))


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} entries must be JSON objects")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise ValueError(f"{label} keys must be strings")
    return cast(dict[str, object], mapping)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Olympus specialist review receipts.")
    parser.add_argument("receipt_file", type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--root", type=Path)
    arguments = parser.parse_args()
    receipts = load_receipts(arguments.receipt_file)
    validate_review_set(
        receipts,
        task_id=arguments.task_id,
        revision=arguments.revision,
        root=arguments.root,
    )
    print(aggregate_odin_status(receipts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
