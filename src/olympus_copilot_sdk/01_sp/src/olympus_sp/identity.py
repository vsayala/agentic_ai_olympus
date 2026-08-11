from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OboIdentity:
    user_id: str
    tenant_id: str
    scopes: frozenset[str]
    access_token: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.user_id or not self.tenant_id or not self.access_token:
            raise ValueError("OBO identity requires user, tenant, and access token")
