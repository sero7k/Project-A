"""Party and custom-game payload builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..common.ids import stable_digest, stable_token
from ..domain.state_helpers import provisioning_flow_enum_value, team_id_for_custom_team


@dataclass(frozen=True)
class PartyPayloadDependencies:
    account_store: Any
    client_version: str
    default_map: str
    default_mode: str
    default_queue: str
    game_pod_id: str
    shooting_range_queue: str
    shooting_range_provisioning_flow: str
    default_profile: Callable[[], dict[str, str]]
    profile_by_key: Callable[[str | None], dict[str, str]]
    party_id_for_profile: Callable[[dict[str, str] | None], str]
    party_profiles: Callable[[dict[str, Any] | None, str | None, dict[str, str] | None], list[dict[str, str]]]
    party_muc_name: Callable[[str], str]
    party_voice_room_id: Callable[[str], str]
    player_identity_payload: Callable[[dict[str, str] | None], dict[str, Any]]
    all_map_paths: Callable[[], list[str]]
    all_mode_paths: Callable[[], list[str]]
    eligible_queue_ids: Callable[[], list[str]]
    active_provisioning_flow: Callable[[dict[str, Any] | None], str]
    active_party_state: Callable[[dict[str, Any] | None], str]
    custom_team_for_profile: Callable[[dict[str, Any] | None, dict[str, str]], str]


def party_member_payload(
    deps: PartyPayloadDependencies,
    profile: dict[str, str] | None = None,
    owner_subject: str | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    owner_subject = owner_subject or profile["subject"]
    return {
        "Subject": profile["subject"],
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "prefDisplayName": profile["display_name"],
        "CompetitiveTier": 0,
        "PlayerIdentity": deps.player_identity_payload(profile),
        "SeasonalBadgeInfo": {},
        "IsOwner": profile["subject"] == owner_subject,
        "QueueEligibleRemainingAccountLevels": 0,
        "Pings": [],
        "IsReady": True,
        "IsModerator": False,
        "UseBroadcastHUD": False,
        "PlatformType": "PC",
    }


def custom_game_configs_payload(
    deps: PartyPayloadDependencies,
    game_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    map_id = (game_state or {}).get("map", deps.default_map)
    mode_id = (game_state or {}).get("mode", deps.default_mode)
    enabled_maps = list(dict.fromkeys([map_id] + deps.all_map_paths()))
    enabled_modes = list(dict.fromkeys([mode_id] + deps.all_mode_paths()))
    use_bots = bool((game_state or {}).get("use_bots", False))
    allow_game_modifiers = bool((game_state or {}).get("allow_game_modifiers", False))
    game_rules = dict((game_state or {}).get("game_rules") or {}) if isinstance((game_state or {}).get("game_rules"), dict) else {}
    custom_name = str((game_state or {}).get("custom_game_name") or "Local Custom")
    custom_description = str((game_state or {}).get("custom_game_description") or "")
    custom_config = {
        "Name": custom_name,
        "name": custom_name,
        "Description": custom_description,
        "description": custom_description,
        "QueueID": deps.default_queue,
        "queueID": deps.default_queue,
        "Map": map_id,
        "map": map_id,
        "Mode": mode_id,
        "mode": mode_id,
        "Enabled": True,
        "enabled": True,
        "UseBots": use_bots,
        "useBots": use_bots,
        "AllowGameModifiers": allow_game_modifiers,
        "allowGameModifiers": allow_game_modifiers,
        "GameRules": game_rules,
        "gameRules": game_rules,
        "EnabledMaps": enabled_maps,
        "enabledMaps": enabled_maps,
        "MapOptions": enabled_maps,
        "mapOptions": enabled_maps,
        "DisabledMaps": [],
        "disabledMaps": [],
        "EnabledModes": enabled_modes,
        "enabledModes": enabled_modes,
        "ModeOptions": enabled_modes,
        "modeOptions": enabled_modes,
    }
    shooting_range_config = {
        "Name": "Shooting Range",
        "name": "Shooting Range",
        "Description": "",
        "description": "",
        "QueueID": deps.shooting_range_queue,
        "queueID": deps.shooting_range_queue,
        "Map": deps.default_map,
        "map": deps.default_map,
        "Mode": deps.default_mode,
        "mode": deps.default_mode,
        "Enabled": True,
        "enabled": True,
        "UseBots": False,
        "useBots": False,
        "AllowGameModifiers": False,
        "allowGameModifiers": False,
        "GameRules": {},
        "gameRules": {},
        "EnabledMaps": [deps.default_map],
        "enabledMaps": [deps.default_map],
        "MapOptions": [deps.default_map],
        "mapOptions": [deps.default_map],
        "DisabledMaps": [],
        "disabledMaps": [],
        "EnabledModes": [deps.default_mode],
        "enabledModes": [deps.default_mode],
        "ModeOptions": [deps.default_mode],
        "modeOptions": [deps.default_mode],
    }
    configs = [custom_config, shooting_range_config]
    game_host = (game_state or {}).get("game_host", "127.0.0.1")
    game_port = int((game_state or {}).get("game_port", 7777) or 7777)
    ping_proxy = f"{game_host}:{game_port}"
    return {
        "Enabled": True,
        "enabled": True,
        "EnabledMaps": enabled_maps,
        "enabledMaps": enabled_maps,
        "MapOptions": enabled_maps,
        "mapOptions": enabled_maps,
        "DisabledMaps": [],
        "disabledMaps": [],
        "EnabledModes": enabled_modes,
        "enabledModes": enabled_modes,
        "ModeOptions": enabled_modes,
        "modeOptions": enabled_modes,
        "Queues": deps.eligible_queue_ids(),
        "queues": deps.eligible_queue_ids(),
        "CustomGameConfigs": configs,
        "customGameConfigs": configs,
        "PingProxyAddress": ping_proxy,
        "pingProxyAddress": ping_proxy,
        "GamePodPingServiceInfo": {deps.game_pod_id: {"Host": game_host, "Port": game_port}},
        "gamePodPingServiceInfo": {deps.game_pod_id: {"host": game_host, "port": game_port}},
    }


def custom_games_payload(
    deps: PartyPayloadDependencies,
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    party_id = deps.party_id_for_profile(profile)
    party = party_payload(deps, game_state, party_id, profile)
    custom_game = {
        "ID": party_id,
        "Id": party_id,
        "id": party_id,
        "PartyID": party_id,
        "partyID": party_id,
        "Name": "Local Custom",
        "name": "Local Custom",
        "CustomGameData": party["CustomGameData"],
        "customGameData": party["CustomGameData"],
        "Members": party["Members"],
        "members": party["Members"],
    }
    return {
        "Games": [custom_game],
        "games": [custom_game],
        "CustomGameData": party["CustomGameData"],
        "customGameData": party["CustomGameData"],
        "CustomGameConfigs": custom_game_configs_payload(deps, game_state),
        "customGameConfigs": custom_game_configs_payload(deps, game_state),
    }


def party_player_payload(
    deps: PartyPayloadDependencies,
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    party_id = party_id or deps.party_id_for_profile(profile)
    invites = [invite_payload(deps, invite) for invite in deps.account_store.invites_for_account(profile["key"])]
    return {
        "Subject": profile["subject"],
        "SessionClientID": stable_token("client", profile["subject"], deps.client_version),
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "prefDisplayName": profile["display_name"],
        "Version": int((game_state or {}).get("party_version", 1)),
        "CurrentPartyID": party_id,
        "Invites": invites,
        "Requests": [],
        "PlatformInfo": {
            "platformType": "PC",
            "platformOS": "Windows",
            "platformOSVersion": "10.0.19045.1.768.64bit",
            "platformChipset": "Unknown",
        },
    }


def party_payload(
    deps: PartyPayloadDependencies,
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or deps.default_profile()
    party_id = party_id or deps.party_id_for_profile(profile)
    map_id = (game_state or {}).get("map", deps.default_map)
    mode_id = (game_state or {}).get("mode", deps.default_mode)
    queue_id = (game_state or {}).get("queue", "")
    map_options = list(dict.fromkeys([map_id] + deps.all_map_paths()))
    mode_options = list(dict.fromkeys([mode_id] + deps.all_mode_paths()))
    provisioning_flow = deps.active_provisioning_flow(game_state)
    provisioning_flow_enum = provisioning_flow_enum_value(provisioning_flow)
    party_state = deps.active_party_state(game_state)
    is_solo_range = queue_id == deps.shooting_range_queue or provisioning_flow in {deps.shooting_range_provisioning_flow, "NewPlayerExperience"}
    max_party_size = 1 if is_solo_range else 10
    use_bots = bool((game_state or {}).get("use_bots", False))
    allow_game_modifiers = bool((game_state or {}).get("allow_game_modifiers", False))
    custom_name = str((game_state or {}).get("custom_game_name") or "Local Custom")
    custom_description = str((game_state or {}).get("custom_game_description") or "")
    game_rules = dict((game_state or {}).get("game_rules") or {}) if isinstance((game_state or {}).get("game_rules"), dict) else {}
    queue_entry_time = str((game_state or {}).get("matchmaking_started_at") or "0001-01-01T00:00:00.000Z")
    profiles = deps.party_profiles(game_state, party_id, profile)
    owner_subject = profiles[0]["subject"] if profiles else profile["subject"]
    team_one = []
    team_two = []
    team_spectate = []
    for profile in profiles:
        team = deps.custom_team_for_profile(game_state, profile)
        team_id = team_id_for_custom_team(team)
        player = {
            "Subject": profile["subject"],
            "GameName": profile["game_name"],
            "TagLine": profile["tag_line"],
            "GameTag": profile["tag_line"],
            "DisplayName": profile["display_name"],
            "displayName": profile["display_name"],
            "prefDisplayName": profile["display_name"],
            "Player": profile["subject"],
            "player": profile["subject"],
            "Puuid": profile["subject"],
            "puuid": profile["subject"],
            "Team": team,
            "team": team,
            "TeamID": team_id,
            "teamID": team_id,
            "teamId": team_id,
        }
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    return {
        "ID": party_id,
        "MUCName": deps.party_muc_name(party_id),
        "VoiceRoomID": deps.party_voice_room_id(party_id),
        "Version": int((game_state or {}).get("party_version", 1)),
        "ClientVersion": deps.client_version,
        "Members": [party_member_payload(deps, profile, owner_subject) for profile in profiles],
        "State": party_state,
        "PreviousState": "DEFAULT",
        "StateTransitionReason": "",
        "Accessibility": (game_state or {}).get("party_accessibility", "CLOSED"),
        "CustomGameData": {
            "Name": custom_name,
            "name": custom_name,
            "Description": custom_description,
            "description": custom_description,
            "Map": map_id,
            "map": map_id,
            "MapID": map_id,
            "mapID": map_id,
            "Mode": mode_id,
            "mode": mode_id,
            "ModeID": mode_id,
            "modeID": mode_id,
            "GameMode": mode_id,
            "gameMode": mode_id,
            "GameModeID": mode_id,
            "gameModeID": mode_id,
            "AllowGameModifiers": allow_game_modifiers,
            "allowGameModifiers": allow_game_modifiers,
            "UseBots": use_bots,
            "useBots": use_bots,
            "BalanceWarnings": [],
            "balanceWarnings": [],
            "Settings": {
                "Map": map_id,
                "MapID": map_id,
                "MapId": map_id,
                "mapId": map_id,
                "MapUrl": map_id,
                "MapURL": map_id,
                "MapPath": map_id,
                "MapOptions": map_options,
                "mapOptions": map_options,
                "EnabledMaps": map_options,
                "enabledMaps": map_options,
                "DisabledMaps": [],
                "disabledMaps": [],
                "Mode": mode_id,
                "ModeID": mode_id,
                "ModeId": mode_id,
                "modeId": mode_id,
                "GameMode": mode_id,
                "GameModeID": mode_id,
                "GameModeId": mode_id,
                "gameModeId": mode_id,
                "ModeOptions": mode_options,
                "modeOptions": mode_options,
                "EnabledModes": mode_options,
                "enabledModes": mode_options,
                "QueueID": queue_id,
                "queueID": queue_id,
                "QueueId": queue_id,
                "queueId": queue_id,
                "ProvisioningFlow": provisioning_flow,
                "provisioningFlow": provisioning_flow,
                "ProvisioningFlowID": provisioning_flow,
                "provisioningFlowID": provisioning_flow,
                "ProvisioningFlowId": provisioning_flow,
                "provisioningFlowId": provisioning_flow,
                "ProvisioningFlowEnum": provisioning_flow_enum,
                "provisioningFlowEnum": provisioning_flow_enum,
                "UseBots": use_bots,
                "useBots": use_bots,
                "AllowGameModifiers": allow_game_modifiers,
                "allowGameModifiers": allow_game_modifiers,
                "Name": custom_name,
                "name": custom_name,
                "Description": custom_description,
                "description": custom_description,
                "GamePod": deps.game_pod_id if party_state != "DEFAULT" else "",
                "GamePodID": deps.game_pod_id if party_state != "DEFAULT" else "",
                "gamePodID": deps.game_pod_id if party_state != "DEFAULT" else "",
                "GameRules": game_rules,
                "gameRules": game_rules,
            },
            "Membership": {
                "TeamOne": team_one,
                "TeamTwo": team_two,
                "TeamSpectate": team_spectate,
                "teamOne": team_one,
                "teamTwo": team_two,
                "teamSpectate": team_spectate,
                "teamOneCoaches": None,
                "teamTwoCoaches": None,
            },
            "MapOptions": map_options,
            "mapOptions": map_options,
            "EnabledMaps": map_options,
            "enabledMaps": map_options,
            "DisabledMaps": [],
            "disabledMaps": [],
            "ModeOptions": mode_options,
            "modeOptions": mode_options,
            "EnabledModes": mode_options,
            "enabledModes": mode_options,
            "MaxPartySize": max_party_size,
            "maxPartySize": max_party_size,
            "AutobalanceEnabled": False,
            "AutobalanceMinPlayers": 0,
            "HasRecoveryData": False,
        },
        "MatchmakingData": {
            "QueueID": queue_id,
            "queueID": queue_id,
            "PreferredGamePods": [deps.game_pod_id] if queue_id else [],
            "SkillDisparityRRPenalty": 0,
            "ProvisioningFlow": provisioning_flow if party_state != "DEFAULT" else "Invalid",
            "provisioningFlow": provisioning_flow if party_state != "DEFAULT" else "Invalid",
        },
        "Invites": [],
        "Requests": [],
        "QueueEntryTime": queue_entry_time,
        "ErrorNotification": {"ErrorType": "", "ErroredPlayers": None},
        "RestrictedSeconds": 0,
        "EligibleQueues": deps.eligible_queue_ids(),
        "eligibleQueues": deps.eligible_queue_ids(),
        "QueueIneligibilities": [],
        "queueIneligibilities": [],
        "CheatData": {"GamePodOverride": "", "ForcePostGameProcessing": False},
        "XPBonuses": [],
        "InviteCode": stable_digest("invite-code", party_id).upper()[:6],
    }


def invite_payload(deps: PartyPayloadDependencies, invite: Any) -> dict[str, Any]:
    inviter = deps.profile_by_key(invite.inviter_account_key)
    invitee = deps.profile_by_key(invite.invitee_account_key)
    return {
        "ID": invite.invite_id,
        "Id": invite.invite_id,
        "id": invite.invite_id,
        "InvitationID": invite.invite_id,
        "invitationID": invite.invite_id,
        "PartyID": invite.party_id,
        "partyID": invite.party_id,
        "PartyId": invite.party_id,
        "partyId": invite.party_id,
        "Inviter": inviter["subject"],
        "inviter": inviter["subject"],
        "InviterSubject": inviter["subject"],
        "inviterSubject": inviter["subject"],
        "InviterGameName": inviter["game_name"],
        "InviterTagLine": inviter["tag_line"],
        "InviterDisplayName": inviter["display_name"],
        "Invitee": invitee["subject"],
        "invitee": invitee["subject"],
        "Subject": invitee["subject"],
        "subject": invitee["subject"],
        "GameName": invitee["game_name"],
        "TagLine": invitee["tag_line"],
        "DisplayName": invitee["display_name"],
        "State": "PENDING",
        "state": "PENDING",
    }


def invites_payload(deps: PartyPayloadDependencies, profile: dict[str, str]) -> dict[str, Any]:
    invites = [invite_payload(deps, invite) for invite in deps.account_store.invites_for_account(profile["key"])]
    return {"Invites": invites, "invites": invites, "Requests": [], "requests": []}
