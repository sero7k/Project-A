"""Queue and matchmaking configuration payload builders."""

from __future__ import annotations

from typing import Any, Callable


def all_map_paths(map_rows: list[dict[str, str]]) -> list[str]:
    excluded = {"Range", "Range NPE"}
    return [row["path"] for row in map_rows if row.get("name") not in excluded]


def all_mode_paths(mode_rows: list[dict[str, str]]) -> list[str]:
    return [row["path"] for row in mode_rows]


def queue_mode_path(
    queue_id: str,
    *,
    shooting_range_queue: str,
    default_mode: str,
    default_matchmaking_queue: str,
) -> str:
    if queue_id == shooting_range_queue:
        return default_mode
    if queue_id in {default_matchmaking_queue, "spikerush"}:
        return "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C"
    return "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C"


def queue_map_paths(
    queue_id: str,
    *,
    shooting_range_queue: str,
    default_map: str,
    map_rows: list[dict[str, str]],
) -> list[str]:
    if queue_id == shooting_range_queue:
        return [default_map]
    return all_map_paths(map_rows)


def queue_config_response(queue: dict[str, Any]) -> dict[str, Any]:
    payload = dict(queue)
    payload.setdefault("Queues", [queue])
    payload.setdefault("queues", [queue])
    payload.setdefault("QueueConfigs", [queue])
    payload.setdefault("queueConfigs", [queue])
    return payload


def queue_config(
    queue_id: str,
    name: str,
    *,
    map_rows: list[dict[str, str]],
    default_map: str,
    default_mode: str,
    default_matchmaking_queue: str,
    shooting_range_queue: str,
    provisioning_flow_enum_value: Callable[[str | None], int],
    default_provisioning_flow: str,
    matchmaking_provisioning_flow: str,
    team_size: int = 5,
    max_party_size: int = 5,
    ranked: bool = False,
    provisioning_flow: str | None = None,
) -> dict[str, Any]:
    provisioning_flow = provisioning_flow or matchmaking_provisioning_flow
    mode_id = queue_mode_path(
        queue_id,
        shooting_range_queue=shooting_range_queue,
        default_mode=default_mode,
        default_matchmaking_queue=default_matchmaking_queue,
    )
    maps = queue_map_paths(
        queue_id,
        shooting_range_queue=shooting_range_queue,
        default_map=default_map,
        map_rows=map_rows,
    )
    return {
        "QueueID": queue_id,
        "queueID": queue_id,
        "QueueId": queue_id,
        "queueId": queue_id,
        "ID": queue_id,
        "id": queue_id,
        "Name": name,
        "name": name,
        "Mode": mode_id,
        "mode": mode_id,
        "ModeID": mode_id,
        "modeID": mode_id,
        "ModeId": mode_id,
        "modeId": mode_id,
        "GameMode": mode_id,
        "gameMode": mode_id,
        "GameModeID": mode_id,
        "gameModeID": mode_id,
        "Enabled": True,
        "enabled": True,
        "IsAvailable": True,
        "isAvailable": True,
        "TeamSize": team_size,
        "teamSize": team_size,
        "MaxPartySize": max_party_size,
        "maxPartySize": max_party_size,
        "MinPartySize": 1,
        "minPartySize": 1,
        "Maps": maps,
        "maps": maps,
        "AllowFullPartyBypassSkillRestrictions": True,
        "allowFullPartyBypassSkillRestrictions": True,
        "IsRanked": ranked,
        "isRanked": ranked,
        "MinimumGamesRequired": 0,
        "minimumGamesRequired": 0,
        "EstimatedWaitTimeSeconds": 0,
        "estimatedWaitTimeSeconds": 0,
        "EstimatedQueueTimeSeconds": 0,
        "estimatedQueueTimeSeconds": 0,
        "PlayersInQueue": 1,
        "playersInQueue": 1,
        "WaitTime": 0,
        "waitTime": 0,
        "QueuesForMinimumGamesEligibility": [],
        "queuesForMinimumGamesEligibility": [],
        "ProvisioningFlow": provisioning_flow,
        "provisioningFlow": provisioning_flow,
        "ProvisioningFlowID": provisioning_flow,
        "provisioningFlowID": provisioning_flow,
        "ProvisioningFlowEnum": provisioning_flow_enum_value(provisioning_flow),
        "provisioningFlowEnum": provisioning_flow_enum_value(provisioning_flow),
    }


def queue_configs_payload(
    *,
    map_rows: list[dict[str, str]],
    default_map: str,
    default_mode: str,
    default_queue: str,
    default_matchmaking_queue: str,
    shooting_range_queue: str,
    default_provisioning_flow: str,
    matchmaking_provisioning_flow: str,
    shooting_range_provisioning_flow: str,
    provisioning_flow_enum_value: Callable[[str | None], int],
) -> dict[str, Any]:
    kwargs = {
        "map_rows": map_rows,
        "default_map": default_map,
        "default_mode": default_mode,
        "default_matchmaking_queue": default_matchmaking_queue,
        "shooting_range_queue": shooting_range_queue,
        "provisioning_flow_enum_value": provisioning_flow_enum_value,
        "default_provisioning_flow": default_provisioning_flow,
        "matchmaking_provisioning_flow": matchmaking_provisioning_flow,
    }
    queues = [
        queue_config(default_queue, "Local Custom", max_party_size=10, ranked=False, provisioning_flow=default_provisioning_flow, **kwargs),
        queue_config(shooting_range_queue, "Shooting Range", team_size=1, max_party_size=1, ranked=False, provisioning_flow=shooting_range_provisioning_flow, **kwargs),
        queue_config(default_matchmaking_queue, "Local Test Queue", max_party_size=5, ranked=False, **kwargs),
        queue_config("unrated", "Local Unrated", max_party_size=5, ranked=False, **kwargs),
        queue_config("competitive", "Local Competitive", max_party_size=5, ranked=True, **kwargs),
        queue_config("spikerush", "Local Spike Rush", max_party_size=5, ranked=False, **kwargs),
    ]
    return {"Queues": queues, "queues": queues, "QueueConfigs": queues, "queueConfigs": queues}
