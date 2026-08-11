from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self, cast
from urllib.parse import urlsplit

EXPECTED_CHANNELS = frozenset({"teams", "microsoft_365_copilot"})
REQUIRED_SCOPES = frozenset({"openid", "profile", "offline_access"})
PLACEHOLDER_PREFIX = "replace_me_"
_SENSITIVE_KEY = re.compile(r"(?:^|_)(?:secret|token|password|credential|private_key)(?:$|_)")
_JWT_VALUE = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


class EvidenceClassification(StrEnum):
    STATIC = "STATIC"
    MOCKED = "MOCKED"
    AUTHENTICATED = "AUTHENTICATED"


@dataclass(frozen=True)
class SignInConsentConfig:
    sign_in_required: bool
    admin_consent_required: bool
    consent_notice: str
    sign_in_label: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        _reject_unknown_keys(
            value,
            {"sign_in_required", "admin_consent_required", "consent_notice", "sign_in_label"},
            "sign_in_consent",
        )
        return cls(
            sign_in_required=_required_bool(value, "sign_in_required"),
            admin_consent_required=_required_bool(value, "admin_consent_required"),
            consent_notice=_required_text(value, "consent_notice"),
            sign_in_label=_required_text(value, "sign_in_label"),
        )


@dataclass(frozen=True)
class FoundryConfig:
    project_endpoint: str
    deployment_name: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        _reject_unknown_keys(value, {"project_endpoint", "deployment_name"}, "foundry")
        endpoint = _required_text(value, "project_endpoint")
        _validate_https_url(endpoint, "foundry.project_endpoint")
        return cls(endpoint, _required_text(value, "deployment_name"))


@dataclass(frozen=True)
class SharePointTestConfig:
    site_url: str
    restricted_item_reference: str
    authorized_principal_label: str
    denied_principal_label: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        _reject_unknown_keys(
            value,
            {
                "site_url",
                "restricted_item_reference",
                "authorized_principal_label",
                "denied_principal_label",
            },
            "sharepoint_test",
        )
        site_url = _required_text(value, "site_url")
        _validate_https_url(site_url, "sharepoint_test.site_url")
        authorized = _required_text(value, "authorized_principal_label")
        denied = _required_text(value, "denied_principal_label")
        if authorized.casefold() == denied.casefold():
            raise ValueError("Authorized and denied test principals must be different")
        return cls(
            site_url=site_url,
            restricted_item_reference=_required_text(value, "restricted_item_reference"),
            authorized_principal_label=authorized,
            denied_principal_label=denied,
        )


@dataclass(frozen=True)
class OwnershipBoundaries:
    channel_ux: str
    retrieval_authorization: str
    agent_tool_semantics: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        _reject_unknown_keys(
            value,
            {"channel_ux", "retrieval_authorization", "agent_tool_semantics"},
            "ownership",
        )
        ownership = cls(
            channel_ux=_required_text(value, "channel_ux"),
            retrieval_authorization=_required_text(value, "retrieval_authorization"),
            agent_tool_semantics=_required_text(value, "agent_tool_semantics"),
        )
        if ownership != cls("hela", "loki", "thor"):
            raise ValueError(
                "Ownership must keep channel UX, retrieval, and agent semantics separate"
            )
        return ownership


@dataclass(frozen=True)
class ChannelExposureConfig:
    schema_version: str
    tenant_id: str
    app_client_id: str
    teams_app_id: str
    microsoft_365_copilot_agent_id: str
    expected_audience: str
    expected_scopes: tuple[str, ...]
    expected_channels: tuple[str, ...]
    sign_in_consent: SignInConsentConfig
    foundry: FoundryConfig
    sharepoint_test: SharePointTestConfig
    ownership: OwnershipBoundaries
    evidence_classification: EvidenceClassification

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        _reject_sensitive_data(value)
        _reject_unknown_keys(
            value,
            {
                "schema_version",
                "tenant_id",
                "app_client_id",
                "teams_app_id",
                "microsoft_365_copilot_agent_id",
                "expected_audience",
                "expected_scopes",
                "expected_channels",
                "sign_in_consent",
                "foundry",
                "sharepoint_test",
                "ownership",
                "evidence_classification",
            },
            "channel configuration",
        )
        scopes = _text_tuple(value, "expected_scopes")
        missing_scopes = REQUIRED_SCOPES - set(scopes)
        if missing_scopes:
            raise ValueError(f"Missing required scopes: {', '.join(sorted(missing_scopes))}")
        channels = _text_tuple(value, "expected_channels")
        missing_channels = EXPECTED_CHANNELS - set(channels)
        if missing_channels:
            raise ValueError(f"Missing required channels: {', '.join(sorted(missing_channels))}")
        evidence = EvidenceClassification(_required_text(value, "evidence_classification"))
        if evidence is EvidenceClassification.AUTHENTICATED and _contains_placeholder(value):
            raise ValueError(
                "AUTHENTICATED evidence cannot contain unresolved replace_me_ placeholders"
            )
        return cls(
            schema_version=_required_text(value, "schema_version"),
            tenant_id=_required_text(value, "tenant_id"),
            app_client_id=_required_text(value, "app_client_id"),
            teams_app_id=_required_text(value, "teams_app_id"),
            microsoft_365_copilot_agent_id=_required_text(value, "microsoft_365_copilot_agent_id"),
            expected_audience=_required_text(value, "expected_audience"),
            expected_scopes=scopes,
            expected_channels=channels,
            sign_in_consent=SignInConsentConfig.from_mapping(
                _required_mapping(value, "sign_in_consent")
            ),
            foundry=FoundryConfig.from_mapping(_required_mapping(value, "foundry")),
            sharepoint_test=SharePointTestConfig.from_mapping(
                _required_mapping(value, "sharepoint_test")
            ),
            ownership=OwnershipBoundaries.from_mapping(_required_mapping(value, "ownership")),
            evidence_classification=evidence,
        )


def load_channel_config(path: Path) -> ChannelExposureConfig:
    payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(payload, dict):
        raise ValueError("Channel configuration must be a JSON object")
    return ChannelExposureConfig.from_mapping(cast(dict[str, object], payload))


def _required_text(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item.strip()


def _required_bool(value: Mapping[str, object], key: str) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise ValueError(f"{key} must be a boolean")
    return item


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be an object")
    return cast(dict[str, object], item)


def _text_tuple(value: Mapping[str, object], key: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, list) or not item:
        raise ValueError(f"{key} must be a non-empty array of strings")
    items = cast(list[object], item)
    if any(not isinstance(entry, str) or not entry.strip() for entry in items):
        raise ValueError(f"{key} must contain only non-empty strings")
    return tuple(cast(str, entry).strip() for entry in items)


def _validate_https_url(value: str, field: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{field} must be an HTTPS URL without embedded credentials")


def _reject_unknown_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    unknown = set(value) - expected
    if unknown:
        raise ValueError(f"Unknown fields in {context}: {', '.join(sorted(unknown))}")


def _reject_sensitive_data(value: object, path: str = "configuration") -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for raw_key, item in mapping.items():
            key = str(raw_key).casefold()
            if _SENSITIVE_KEY.search(key):
                raise ValueError(f"Secrets or tokens are not allowed: {path}.{raw_key}")
            _reject_sensitive_data(item, f"{path}.{raw_key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        sequence = cast(Sequence[object], value)
        for index, item in enumerate(sequence):
            _reject_sensitive_data(item, f"{path}[{index}]")
    elif isinstance(value, str):
        normalized = value.strip()
        if normalized.casefold().startswith("bearer ") or _JWT_VALUE.fullmatch(normalized):
            raise ValueError(f"Secrets or tokens are not allowed: {path}")


def _contains_placeholder(value: object) -> bool:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return any(_contains_placeholder(item) for item in mapping.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        sequence = cast(Sequence[object], value)
        return any(_contains_placeholder(item) for item in sequence)
    return isinstance(value, str) and PLACEHOLDER_PREFIX in value.casefold()
