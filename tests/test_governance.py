from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from olympus_copilot_sdk.governance.receipts import (
    ReviewReceipt,
    aggregate_odin_status,
    calculate_artifact_hash,
    validate_review_set,
)


def _receipt(specialist: str, base_artifact_hash: str, **overrides: object) -> ReviewReceipt:
    payload: dict[str, object] = {
        "contract_version": "1.0",
        "task_id": "task-123",
        "revision": "abc123",
        "specialist": specialist,
        "scope": ["artifact.txt"],
        "status": "PASS",
        "findings": [],
        "conditions": [],
        "evidence": [{"reference": "artifact.txt:1", "claim": "Reviewed content"}],
        "checks": [{"command": "pytest", "outcome": "PASS"}],
        "artifact_hash": base_artifact_hash,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "challenge_round": 0,
    }
    payload.update(overrides)
    return ReviewReceipt.from_mapping(payload)


def test_complete_current_review_set_passes(tmp_path: Path) -> None:
    (tmp_path / "artifact.txt").write_text("reviewed", encoding="utf-8")
    artifact_hash = calculate_artifact_hash(tmp_path, ["artifact.txt"])
    receipts = tuple(_receipt(name, artifact_hash) for name in ("loki", "thor", "hela"))

    validate_review_set(
        receipts,
        task_id="task-123",
        revision="abc123",
        root=tmp_path,
    )

    assert aggregate_odin_status(receipts) == "ODIN PASS"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"revision": "old"}, "Stale revision"),
        ({"artifact_hash": "0" * 64}, "Stale artifact hash"),
    ],
)
def test_stale_receipt_is_rejected(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    (tmp_path / "artifact.txt").write_text("reviewed", encoding="utf-8")
    artifact_hash = calculate_artifact_hash(tmp_path, ["artifact.txt"])
    receipts = tuple(
        _receipt(name, artifact_hash, **(overrides if name == "loki" else {}))
        for name in ("loki", "thor", "hela")
    )

    with pytest.raises(ValueError, match=message):
        validate_review_set(
            receipts,
            task_id="task-123",
            revision="abc123",
            root=tmp_path,
        )


def test_missing_specialist_forces_blocked_status(tmp_path: Path) -> None:
    (tmp_path / "artifact.txt").write_text("reviewed", encoding="utf-8")
    artifact_hash = calculate_artifact_hash(tmp_path, ["artifact.txt"])
    receipts = tuple(_receipt(name, artifact_hash) for name in ("loki", "thor"))

    with pytest.raises(ValueError, match="Missing specialist receipts: hela"):
        validate_review_set(receipts, task_id="task-123", revision="abc123")
    assert aggregate_odin_status(receipts) == "ODIN BLOCKED"


def test_non_pass_receipt_requires_an_explicit_condition() -> None:
    with pytest.raises(ValueError, match="must contain at least one condition"):
        _receipt("loki", "0" * 64, status="BLOCKED")


def test_challenge_round_is_bounded() -> None:
    with pytest.raises(ValueError, match="challenge_round must be between 0 and 2"):
        _receipt("loki", "0" * 64, challenge_round=3)


def test_agent_topology_keeps_odin_as_the_only_coordinator() -> None:
    root = Path(__file__).parents[1]
    agents = root / ".github" / "agents"

    odin = (agents / "odin.agent.md").read_text(encoding="utf-8")
    assert "agents: [loki, thor, hela]" in odin
    assert "governance.receipts" in odin

    for specialist in ("loki", "thor", "hela"):
        contract = (agents / f"{specialist}.agent.md").read_text(encoding="utf-8")
        assert "agents: []" in contract
        assert "exactly one fenced `json` block" in contract
        assert "contract-version `1.0` receipt" in contract
