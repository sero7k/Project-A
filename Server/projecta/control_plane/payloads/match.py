"""Pregame and core-game payload builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..common.ids import stable_token
from ..domain.state_helpers import provisioning_flow_enum_value, team_id_for_custom_team


@dataclass(frozen=True)
class MatchPayloadDependencies:
    match_id: str
    game_pod_id: str
    default_map: str
    default_mode: str
    default_queue: str
    default_character_id: str
    team_voice_id: str
    team_muc_name: str
    all_muc_name: str
    default_profile: Callable[[], dict[str, str]]
    party_id_for_profile: Callable[[dict[str, str] | None], str]
    party_profiles: Callable[[dict[str, Any] | None, str | None, dict[str, str] | None], list[dict[str, str]]]
    player_identity_payload: Callable[[dict[str, str] | None], dict[str, Any]]
    active_provisioning_flow: Callable[[dict[str, Any] | None], str]
    custom_team_for_profile: Callable[[dict[str, Any] | None, dict[str, str]], str]
    character_for_profile: Callable[[dict[str, Any], dict[str, str], str], str]
    character_state_for_profile: Callable[[dict[str, Any], dict[str, str]], str]
    pregame_character_selection_state: Callable[[dict[str, Any], dict[str, str], dict[str, str]], str]
    utc_now: Callable[[], str]


def pregame_player_payload(
    deps: MatchPayloadDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": deps.match_id,
        "Version": int(game_state.get("match_version", 1)),
        "CharacterID": deps.character_for_profile(game_state, profile, ""),
        "characterID": deps.character_for_profile(game_state, profile, ""),
        "CharacterSelectionState": deps.pregame_character_selection_state(game_state, profile, profile),
        "characterSelectionState": deps.pregame_character_selection_state(game_state, profile, profile),
        "PregamePlayerState": "joined",
        "pregamePlayerState": "joined",
        "CompetitiveTier": 0,
        "competitiveTier": 0,
        "PlayerIdentity": deps.player_identity_payload(profile),
        "playerIdentity": deps.player_identity_payload(profile),
    }


def inactive_match_player_payload(
    deps: MatchPayloadDependencies,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": "",
        "Version": 0,
    }


def inactive_match_payload(deps: MatchPayloadDependencies) -> dict[str, Any]:
    empty_ally_team = {"TeamID": "", "Players": []}
    empty_enemy_team = {"TeamID": "", "Players": []}
    return {
        "ID": "",
        "MatchID": "",
        "Version": 0,
        "Teams": [],
        "AllyTeam": empty_ally_team,
        "EnemyTeam": empty_enemy_team,
        "ObserverSubjects": [],
        "MatchCoaches": [],
        "PregameState": "Invalid",
        "MapID": "",
        "Map": "",
        "MapUrl": "",
        "MapURL": "",
        "Mode": "",
        "ModeID": "",
        "GameMode": "",
        "GameModeID": "",
        "EnemyTeamLockCount": 0,
        "EnemyTeamSize": 0,
        "LastUpdated": deps.utc_now(),
        "VoiceSessionID": "",
        "MUCName": "",
        "QueueID": "",
        "ProvisioningFlowID": "",
        "ProvisioningFlowEnum": "Invalid",
        "IsRanked": False,
        "PhaseTimeRemainingNS": 0,
        "ProvisioningFlow": "Invalid",
        "ConnectionDetails": None,
        "Players": [],
        "TeamOne": [],
        "TeamTwo": [],
        "TeamSpectate": [],
    }


def pregame_match_payload(
    deps: MatchPayloadDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    viewer_profile = profile or deps.default_profile()
    map_id = game_state.get("map", deps.default_map)
    mode_id = game_state.get("mode", deps.default_mode)
    queue_id = game_state.get("queue", deps.default_queue)
    provisioning_flow = deps.active_provisioning_flow(game_state)
    provisioning_flow_enum = provisioning_flow_enum_value(provisioning_flow)
    pregame_state = str(game_state.get("pregame_state") or "")
    if not pregame_state:
        pregame_state = "provisioned" if game_state.get("phase") == "core" else "character_select_active"
    profiles = deps.party_profiles(game_state, deps.party_id_for_profile(viewer_profile), viewer_profile)
    all_locked = all(deps.character_state_for_profile(game_state, member_profile) == "locked" for member_profile in profiles)
    if all_locked and pregame_state != "provisioned":
        pregame_state = "character_select_finished" if game_state.get("phase") != "core" else "provisioned"
    provisioning_state = "provisioned" if game_state.get("phase") == "core" or pregame_state == "provisioned" else ""
    phase_time_remaining_ns = 0 if pregame_state in {"character_select_finished", "provisioned"} else 45_000_000_000
    players = []
    team_one = []
    team_two = []
    team_spectate = []
    for member_profile in profiles:
        team = deps.custom_team_for_profile(game_state, member_profile)
        player = {
            "Subject": member_profile["subject"],
            "TeamID": team_id_for_custom_team(team),
            "CharacterID": deps.character_for_profile(game_state, member_profile, ""),
            "CharacterSelectionState": deps.pregame_character_selection_state(game_state, member_profile, viewer_profile),
            "PregamePlayerState": "joined",
            "CompetitiveTier": 0,
            "PlayerIdentity": deps.player_identity_payload(member_profile),
            "SeasonalBadgeInfo": None,
            "IsCaptain": member_profile["subject"] == profiles[0]["subject"],
        }
        players.append(player)
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    ally_team = {"TeamID": "Blue", "Players": team_one or players}
    enemy_team = {"TeamID": "Red", "Players": team_two}
    teams = [ally_team, enemy_team]
    return {
        "ID": deps.match_id,
        "MatchID": deps.match_id,
        "Version": int(game_state.get("match_version", 1)),
        "Teams": teams,
        "AllyTeam": ally_team,
        "EnemyTeam": enemy_team,
        "ObserverSubjects": [],
        "MatchCoaches": [],
        "Players": players,
        "TeamOne": team_one,
        "TeamTwo": team_two,
        "TeamSpectate": team_spectate,
        "EnemyTeamSize": len(team_two),
        "EnemyTeamLockCount": sum(1 for player in team_two if player.get("CharacterSelectionState") == "locked"),
        "PregameState": pregame_state,
        "LastUpdated": deps.utc_now(),
        "MapID": map_id,
        "Map": map_id,
        "MapUrl": map_id,
        "MapURL": map_id,
        "MapPath": map_id,
        "MapSelectPool": [],
        "BannedMapIDs": [],
        "CastedVotes": None,
        "MapSelectSteps": [],
        "MapSelectStep": 0,
        "Team1": "Blue",
        "GamePodID": deps.game_pod_id,
        "GamePod": deps.game_pod_id,
        "Mode": mode_id,
        "ModeID": mode_id,
        "GameMode": mode_id,
        "GameModeID": mode_id,
        "VoiceSessionID": deps.team_voice_id,
        "MUCName": deps.team_muc_name,
        "QueueID": queue_id,
        "Queue": queue_id,
        "ProvisioningFlowID": provisioning_flow,
        "provisioningFlowID": provisioning_flow,
        "ProvisioningFlowId": provisioning_flow,
        "provisioningFlowId": provisioning_flow,
        "ProvisioningFlowEnum": provisioning_flow_enum,
        "ProvisioningFlow": provisioning_flow,
        "provisioningFlow": provisioning_flow,
        "IsRanked": False,
        "PhaseTimeRemainingNS": phase_time_remaining_ns,
        "ProvisioningState": provisioning_state,
        "provisioningState": provisioning_state,
        "ConnectionDetails": None,
        "DirectConnectSettings": None,
        "IsValid": True,
    }


def core_game_player_payload(
    deps: MatchPayloadDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": deps.match_id,
        "Version": int(game_state.get("match_version", 1)),
    }


def core_game_match_payload(
    deps: MatchPayloadDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    host = game_state.get("game_host", "127.0.0.1")
    port = int(game_state.get("game_port", 7777))
    map_id = game_state.get("map", deps.default_map)
    mode_id = game_state.get("mode", deps.default_mode)
    queue_id = game_state.get("queue", deps.default_queue)
    provisioning_flow = deps.active_provisioning_flow(game_state)
    players = []
    team_one = []
    team_two = []
    team_spectate = []
    player_key = stable_token("player-key", deps.match_id, profile["subject"])
    for member_profile in deps.party_profiles(game_state, deps.party_id_for_profile(profile), profile):
        team = deps.custom_team_for_profile(game_state, member_profile)
        player = {
            "Subject": member_profile["subject"],
            "TeamID": team_id_for_custom_team(team),
            "CharacterID": deps.character_for_profile(game_state, member_profile, deps.default_character_id),
            "PlayerIdentity": deps.player_identity_payload(member_profile),
            "SeasonalBadgeInfo": None,
            "IsCoach": False,
        }
        players.append(player)
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    return {
        "MatchID": deps.match_id,
        "ID": deps.match_id,
        "Version": int(game_state.get("match_version", 1)),
        "State": "IN_PROGRESS",
        "MapID": map_id,
        "Map": map_id,
        "MapUrl": map_id,
        "MapURL": map_id,
        "MapPath": map_id,
        "MatchMap": map_id,
        "ModeID": mode_id,
        "Mode": mode_id,
        "GameMode": mode_id,
        "GameModeID": mode_id,
        "ProvisioningFlow": provisioning_flow,
        "provisioningFlow": provisioning_flow,
        "ProvisioningState": "provisioned",
        "QueueID": queue_id,
        "GamePodID": deps.game_pod_id,
        "GamePod": deps.game_pod_id,
        "AllMUCName": deps.all_muc_name,
        "TeamMUCName": deps.team_muc_name,
        "TeamVoiceID": deps.team_voice_id,
        "IsReconnectable": True,
        "ConnectionDetails": {
            "GameServerHosts": [host],
            "GameServerHost": host,
            "gameServerHost": host,
            "GameServerAddress": host,
            "gameServerAddress": host,
            "GameServerPort": port,
            "gameServerPort": port,
            "ServerAddress": host,
            "serverAddress": host,
            "ServerIP": host,
            "serverIP": host,
            "serverIp": host,
            "ServerPort": port,
            "serverPort": port,
            "GamePodID": deps.game_pod_id,
            "gamePodID": deps.game_pod_id,
            "GamePod": deps.game_pod_id,
            "gamePod": deps.game_pod_id,
            "GameServerObfuscatedIP": 0,
            "gameServerObfuscatedIP": 0,
            "GameClientHash": 0,
            "gameClientHash": 0,
            "PlayerKey": player_key,
            "playerKey": player_key,
        },
        "DirectConnectSettings": {
            "Player": profile["subject"],
            "player": profile["subject"],
            "Subject": profile["subject"],
            "subject": profile["subject"],
            "PlayerName": profile["game_name"],
            "playerName": profile["game_name"],
            "ServerIP": host,
            "serverIP": host,
            "ServerAddress": host,
            "serverAddress": host,
            "Port": port,
            "port": port,
            "ServerPort": port,
            "serverPort": port,
        },
        "Players": players,
        "TeamOne": team_one,
        "TeamTwo": team_two,
        "TeamSpectate": team_spectate,
        "MatchmakingData": {
            "QueueID": queue_id,
            "queueID": queue_id,
            "PreferredGamePods": [deps.game_pod_id],
            "GamePodID": deps.game_pod_id,
            "ProvisioningFlow": provisioning_flow,
            "provisioningFlow": provisioning_flow,
        },
        "PostGameDetails": None,
    }
