"""Backend readiness state helpers for party, pregame, and core channels."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


KeyNormalizer = Callable[[str | None], str]


def _identity_key(value: str | None) -> str:
    return str(value or "")


def mark_backend_ready(game_state: dict[str, Any] | None, profile: dict[str, str], channel: str) -> bool:
    if not game_state:
        return False
    key_name = f"{channel}_ready_keys"
    values = game_state.setdefault(key_name, [])
    if not isinstance(values, list):
        values = []
        game_state[key_name] = values
    key = profile["key"]
    if key in values:
        return False
    values.append(key)
    values.sort()
    return True


def backend_ready(game_state: dict[str, Any] | None, profile: dict[str, str], channel: str) -> bool:
    if not game_state:
        return False
    values = game_state.get(f"{channel}_ready_keys")
    return isinstance(values, list) and profile["key"] in values


def set_backend_ready_keys(
    game_state: dict[str, Any] | None,
    channel: str,
    profiles: Iterable[dict[str, str]],
    normalize_key: KeyNormalizer = _identity_key,
) -> None:
    if not game_state:
        return
    key_name = f"{channel}_ready_keys"
    ready = sorted({normalize_key(str(profile.get("key") or "")) for profile in profiles if profile.get("key")})
    game_state[key_name] = ready


def clear_backend_ready_channels(game_state: dict[str, Any] | None, *channels: str) -> None:
    if not game_state:
        return
    for channel in channels:
        game_state[f"{channel}_ready_keys"] = []


def prime_backend_state_for_phase(
    game_state: dict[str, Any] | None,
    profiles: Iterable[dict[str, str]],
    phase: str,
    normalize_key: KeyNormalizer = _identity_key,
) -> None:
    if not game_state:
        return
    normalized = str(phase or "").lower()
    if normalized == "pregame":
        set_backend_ready_keys(game_state, "pregame", profiles, normalize_key)
        clear_backend_ready_channels(game_state, "party", "core")
        return
    if normalized == "core":
        set_backend_ready_keys(game_state, "pregame", profiles, normalize_key)
        set_backend_ready_keys(game_state, "core", profiles, normalize_key)
        clear_backend_ready_channels(game_state, "party")
        return
    clear_backend_ready_channels(game_state, "pregame", "core")
