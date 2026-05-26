"""Pure state and request-shape helpers for party/match flows."""

from __future__ import annotations

from typing import Any


def normalize_custom_team(team: str | None) -> str:
    normalized = (team or "").strip()
    aliases = {
        "teamone": "TeamOne",
        "one": "TeamOne",
        "blue": "TeamOne",
        "teamtwo": "TeamTwo",
        "two": "TeamTwo",
        "red": "TeamTwo",
        "teamspectate": "TeamSpectate",
        "spectate": "TeamSpectate",
        "spectator": "TeamSpectate",
    }
    if normalized in {"TeamOne", "TeamTwo", "TeamSpectate"}:
        return normalized
    return aliases.get(normalized.lower(), "TeamOne")


def team_id_for_custom_team(team: str) -> str:
    if team == "TeamTwo":
        return "Red"
    if team == "TeamSpectate":
        return "Spectate"
    return "Blue"


def subject_from_team_request(body: dict[str, Any], fallback: str) -> str:
    for key in (
        "playerToPutOnTeam",
        "PlayerToPutOnTeam",
        "Subject",
        "subject",
        "Puuid",
        "puuid",
        "Player",
        "player",
        "PlayerID",
        "PlayerId",
        "playerID",
        "playerId",
    ):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = subject_from_team_request(value, "")
            if nested:
                return nested
    return fallback


def provisioning_flow_enum_value(flow: str | None) -> int:
    mapping = {
        "Invalid": 0,
        "ShootingRange": 1,
        "SkillTest": 2,
        "CustomGame": 3,
        "Matchmaking": 4,
        "NewPlayerExperience": 5,
    }
    return mapping.get(str(flow or ""), 0)


def request_settings_from_body(body: dict[str, Any]) -> dict[str, Any]:
    settings = body.get("Settings") if isinstance(body.get("Settings"), dict) else body
    for container_key in ("CustomGameData", "customGameData", "GameSettings", "gameSettings", "Config", "config"):
        container = body.get(container_key)
        if isinstance(container, dict):
            nested = container.get("Settings") or container.get("settings") or container
            if isinstance(nested, dict):
                return nested
    return settings if isinstance(settings, dict) else body


def first_string(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
