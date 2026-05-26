"""Stable local identifiers and token helpers."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any


SERVICE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-control-plane")


def service_uuid(name: str) -> str:
    return str(uuid.uuid5(SERVICE_NAMESPACE, name))


def stable_digest(*parts: Any) -> str:
    raw = "\0".join(str(part) for part in parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def stable_token(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{stable_digest(prefix, *parts)[:32]}"


def account_token(kind: str, profile: dict[str, str]) -> str:
    return f"{kind}-{profile['key']}-{stable_digest(kind, profile['subject'])[:24]}"
