from __future__ import annotations

from pathlib import Path

from olympus_sp.config import RetrievalMode, SharePointConfig, load_config
from olympus_sp.contracts import RetrievalResult
from olympus_sp.identity import OboIdentity
from olympus_sp.retrieval import AccessDeniedError, SharePointRetriever, SourceRecord
from olympus_sp.tools import SharePointEvidenceTool


class FakeGraphBackend:
    def __init__(self, denied: bool = False) -> None:
        self.denied = denied
        self.token = ""

    def search(self, **values: object) -> list[SourceRecord]:
        self.token = str(values["user_access_token"])
        if self.denied:
            raise AccessDeniedError("restricted")
        return [SourceRecord("item-1", "https://example.test/item-1", "Policy", 0.9, {})]


def _config(mode: RetrievalMode = RetrievalMode.GRAPH) -> SharePointConfig:
    return SharePointConfig(
        "tenant-1",
        "site-1",
        "library-1",
        mode,
        "connection-1",
        "https://graph.microsoft.test/retrieval",
    )


def _identity() -> OboIdentity:
    return OboIdentity("user-1", "tenant-1", frozenset({"Sites.Selected"}), "obo-token")


def test_authorized_user_receives_normalized_evidence_with_obo_token() -> None:
    backend = FakeGraphBackend()
    identity = _identity()
    result = SharePointEvidenceTool(SharePointRetriever(_config(), identity, backend)).retrieve(
        "policy"
    )

    assert backend.token == identity.access_token
    assert result.evidence[0].source_id == "item-1"
    assert not result.access_denied


def test_unauthorized_user_receives_no_restricted_evidence() -> None:
    result = SharePointRetriever(_config(), _identity(), FakeGraphBackend(denied=True)).search(
        "restricted policy"
    )

    assert result == RetrievalResult((), True, "source_access_denied")


def test_config_loads_dedicated_library_placeholders() -> None:
    path = Path(__file__).parents[1] / "configs" / "example.toml"
    config = load_config(path)
    assert config.mode is RetrievalMode.GRAPH
    assert config.library_id == "<dedicated-test-library-id>"


def test_identity_rejects_cross_tenant_context() -> None:
    identity = OboIdentity("user-1", "other-tenant", frozenset(), "token")
    try:
        SharePointRetriever(_config(), identity, FakeGraphBackend())
    except ValueError as error:
        assert "tenant" in str(error)
    else:
        raise AssertionError("cross-tenant OBO context was accepted")
