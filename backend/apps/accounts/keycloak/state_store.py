"""Temporary OIDC state/nonce/verifier storage (server-side, short TTL)."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

PREFIX = "kc_oidc:"
TTL_SECONDS = 600  # 10 minutes


@dataclass
class OidcFlowState:
    state: str
    nonce: str
    code_verifier: str
    next_path: str | None = None


def _key(state: str) -> str:
    return f"{PREFIX}{state}"


def create_flow_state(next_path: str | None) -> OidcFlowState:
    flow = OidcFlowState(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),
        next_path=next_path if (next_path and next_path.startswith("/")) else None,
    )
    cache.set(_key(flow.state), flow.__dict__, TTL_SECONDS)
    return flow


def pop_flow_state(state: str) -> dict[str, Any] | None:
    if not state:
        return None
    k = _key(state)
    data = cache.get(k)
    if data is None:
        return None
    cache.delete(k)
    return data
