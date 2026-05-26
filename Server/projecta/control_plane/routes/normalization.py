"""Route path normalization for service-prefixed control-plane endpoints."""

from __future__ import annotations


SERVICE_PREFIXES = (
    "/ares-parties",
    "/ares-pregame",
    "/ares-contracts",
    "/ares-personalization",
)


def normalize_route_path(path: str) -> str:
    """Map transport/service aliases onto the local route namespace."""
    route_path = _normalize_core_game_path(path)
    if route_path == path:
        route_path = _strip_service_prefix(path)
    return _normalize_legacy_party_path(route_path)


def _normalize_core_game_path(path: str) -> str:
    if not path.startswith("/ares-core-game/"):
        return path

    suffix = path[len("/ares-core-game/") :]
    if suffix.startswith("core-game/"):
        return f"/{suffix}"
    if suffix.startswith("v1/"):
        return f"/core-game/{suffix}"
    return f"/core-game/v1/matches/{suffix}"


def _strip_service_prefix(path: str) -> str:
    for prefix in SERVICE_PREFIXES:
        if path.startswith(f"{prefix}/"):
            return path[len(prefix) :]
    return path


def _normalize_legacy_party_path(path: str) -> str:
    if path.startswith("/v1/parties"):
        return "/parties/v1/parties" + path[len("/v1/parties") :]
    if path.startswith("/v1/players"):
        return "/parties/v1/players" + path[len("/v1/players") :]
    return path
