"""Bootstrap/client payload helpers."""

from __future__ import annotations

from typing import Any

from ..common.ids import account_token


def access_token_payload(profile: dict[str, str]) -> dict[str, Any]:
    token = account_token("access-token", profile)
    return {
        "AccessToken": token,
        "accessToken": token,
        "access_token": token,
        "Token": token,
        "token": token,
        "Expiration": "2099-01-01T00:00:00.000Z",
        "expires_in": 3600,
    }


def entitlements_token_payload(profile: dict[str, str], owned: dict[str, Any]) -> dict[str, Any]:
    token = account_token("entitlements-token", profile)
    return {
        "Token": token,
        "token": token,
        "entitlements_token": token,
        "Entitlements": owned["Entitlements"],
        "entitlements": owned["entitlements"],
        "OwnedEntitlements": owned["OwnedEntitlements"],
        "ownedEntitlements": owned["ownedEntitlements"],
        "OwnedItems": owned["OwnedItems"],
        "ownedItems": owned["ownedItems"],
    }


def config_payload(base: str, *, client_version: str, feedback_locale: str, feedback_shard: str) -> dict[str, Any]:
    collapsed = {
        "SERVICEURL_AGGSTATS": base,
        "SERVICEURL_CHAT": base,
        "SERVICEURL_CONTENT": base,
        "SERVICEURL_CONTRACT_DEFINITIONS": base,
        "SERVICEURL_CONTRACTS": base,
        "SERVICEURL_COREGAME": base,
        "SERVICEURL_FRIENDS": base,
        "SERVICEURL_LATENCY": base,
        "SERVICEURL_MATCHDETAILS": base,
        "SERVICEURL_MATCHHISTORY": base,
        "SERVICEURL_MATCHMAKING": base,
        "SERVICEURL_MMR": base,
        "SERVICEURL_NAME": base,
        "SERVICEURL_PARTY": base,
        "SERVICEURL_PATCHNOTES": base,
        "SERVICEURL_PERSONALIZATION": base,
        "SERVICEURL_PLAYERFEEDBACK": base,
        "SERVICEURL_PREGAME": base,
        "SERVICEURL_RESTRICTIONS": base,
        "SERVICEURL_SESSION": base,
        "SERVICEURL_SOCIAL": base,
        "SERVICEURL_STORE": base,
        "GAME_ROAMINGSETTINGS_ENABLED": False,
        "chat.enabled": True,
        "chat.affinities.enabled": True,
        "collection.playercards.enabled": True,
        "collection.playertitles.enabled": True,
        "content.maps.disabled": False,
        "customgame.config.interval": 30,
        "friends.enabled": True,
        "gnt.enabled": True,
        "matchmaking.testqueue.enabled": True,
        "partyinvites.enabled": True,
        "queue.competitive.default": "competitive",
        "queue.status.config.interval": 30,
        "queue.status.enabled": True,
        "queue.status.update.interval": 30,
        "rchat-blocking.enabled": True,
        "social.enabled": True,
        "playerFeedbackToolURL": base,
        "playerFeedbackToolAccessURL": base,
        "playerFeedbackToolLocale": feedback_locale,
        "playerFeedbackToolShard": feedback_shard,
        "playerfeedbacktool.accessurl": base,
        "playerfeedbacktool.url": base,
        "playerfeedbacktool.locale": feedback_locale,
        "playerfeedbacktool.shard": feedback_shard,
        "playerfeedbacktool.enabled": True,
        "antiAddiction.allowFailures": True,
        "playtime.notifications.enabled": False,
        "playtime.restricted": False,
        "vanguard.enabled": False,
        "vanguard.required": False,
        "anticheat.enabled": False,
        "anticheat.required": False,
        "ares.vanguard.enabled": False,
        "ares.vanguard.required": False,
        "ares.anticheat.enabled": False,
        "ares.anticheat.required": False,
        "partyinvites.enabled": True,
        "customgame.config.interval": 300,
        "ping.useGamePodsFromParties": False,
        "ping.gamePods": "",
    }
    payload = {"LastApplication": "ares", "Collapsed": collapsed}
    payload.update(collapsed)
    return payload


def process_control_payload(headers: Any) -> dict[str, Any]:
    pid = 1
    for key in ("x-riot-clientpid", "x-process-id", "x-riot-pid"):
        raw = headers.get(key)
        if raw and raw.isdigit():
            pid = int(raw)
            break
    return {
        "name": "Riot Client",
        "pid": pid,
        "processId": pid,
        "id": pid,
        "state": "Running",
        "status": "Running",
        "isRunning": True,
        "running": True,
        "started": True,
        "exited": False,
        "exitCode": 0,
        "commandLine": "",
    }


def plugin_manager_payload(client_version: str) -> dict[str, Any]:
    plugins = [
        {"name": "rso-auth", "state": "running", "status": "running", "running": True, "version": client_version},
        {"name": "riot-messaging-service", "state": "running", "status": "running", "running": True, "version": client_version},
        {"name": "process-control", "state": "running", "status": "running", "running": True, "version": client_version},
        {"name": "config-service", "state": "running", "status": "running", "running": True, "version": client_version},
        {"name": "vanguard", "state": "running", "status": "running", "running": True, "version": client_version},
    ]
    return {
        "state": "PluginsInitialized",
        "status": "PluginsInitialized",
        "initializationState": "PluginsInitialized",
        "isInitialized": True,
        "plugins": plugins,
        "pluginStatuses": {p["name"]: p["state"] for p in plugins},
    }
