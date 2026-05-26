#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "reverse-logs" / "test-artifacts"
CHARACTER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ITEM_TYPE_SKIN = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"
ITEM_ID = "27f21d97-4c4b-bd1c-1f08-31830ab0be84"
CONTRACT_ID = "90a1aaa8-f6dc-42f7-ae65-181c9fd0d80b"
PROGRESSION_ID = "11111111-2222-3333-4444-555555555555"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class Client:
    def __init__(self, port: int, account: str = "matrix-user") -> None:
        self.port = port
        self.account = account

    def request(self, method: str, path: str, body: Any = None, account: str | None = None) -> tuple[int, Any]:
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["content-type"] = "application/json"
        token = base64.b64encode(f"riot:{account or self.account}".encode("utf-8")).decode("ascii")
        headers["authorization"] = "Basic " + token
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw.decode("utf-8", "replace")
            return resp.status, parsed


def assert_ok(result: tuple[int, Any], method: str, path: str, required_key: str | None = None) -> Any:
    status, payload = result
    assert 200 <= status < 300, (method, path, status, payload)
    assert not (isinstance(payload, dict) and set(payload) == {"ok", "path"}), (method, path, "fell through catch-all", payload)
    if required_key:
        assert isinstance(payload, dict) and required_key in payload, (method, path, required_key, payload)
    return payload


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    log = ARTIFACT_DIR / "endpoint_matrix.jsonl"
    proc = subprocess.Popen([
        sys.executable, str(ROOT / "Server" / "project_a_server.py"),
        "--port", str(port),
        "--log", str(log),
        "--cert", str(ARTIFACT_DIR / "endpoint_matrix.crt"),
        "--key", str(ARTIFACT_DIR / "endpoint_matrix.key"),
        "--ca-cert", str(ARTIFACT_DIR / "endpoint_matrix_ca.crt"),
        "--allow-memory-db",
        "--reset-state",
        "--account-key", "matrix-user",
        "--riot-name", "MatrixUser",
        "--tag-line", "EUW",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    client = Client(port)
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise RuntimeError(f"server exited early\nSTDOUT={out}\nSTDERR={err}")
            try:
                client.request("GET", "/process-control/v1/process")
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not start")

        account = assert_ok(client.request("GET", "/local/v1/account"), "GET", "/local/v1/account", "Subject")
        subject = account["Subject"]
        party_id = account["partyId"]
        assert_ok(client.request("POST", "/local/v1/accounts", {"account_key": "other-user", "game_name": "OtherUser", "tag_line": "NA1"}), "POST", "/local/v1/accounts", "Subject")

        matrix: list[tuple[str, str, Any, str | None]] = [
            ("GET", "/process-control/v1/process", None, "pid"),
            ("PUT", "/riotclient/region-locale", {"region": "na", "locale": "en_US"}, "region"),
            ("GET", "/rso-auth/v1/authorization/access-token", None, "AccessToken"),
            ("GET", "/entitlements/v1/token", None, "Token"),
            ("GET", "/metadata/v1/", None, "ClientVersion"),
            ("GET", "/anti-addiction/v1/products/ares/policies/playtime/anti-addiction-state", None, "CanPlay"),
            ("GET", "/anti-addiction/v1/products/ares/policies/shutdown/anti-addiction-state", None, "CanPlay"),
            ("GET", "/anti-addiction/v1/products/ares/policies/warningMessage/anti-addiction-state", None, "CanPlay"),
            ("GET", "/eula/v1/agreement/content", None, "content"),
            ("GET", "/eula/v1/privacy-policy/content", None, "content"),
            ("POST", "/product-integration/v1/app-repair/apply", {"RepairCode": "noop"}, "Success"),
            ("GET", "/v1/config/na", None, "Collapsed"),
            ("GET", "/content-service/v2/content", None, "Characters"),
            ("GET", "/contract-definitions/v2/definitions/story", None, "ActiveStoryContractDefinition"),
            ("GET", "/contract-definitions/v2/definitions", None, "ContractDefinitions"),
            ("GET", "/contract-definitions/v2/item-upgrades", None, "ItemUpgrades"),
            ("GET", f"/contracts/v1/contracts/{subject}", None, "Contracts"),
            ("POST", f"/contracts/v1/contracts/{subject}/special/{CONTRACT_ID}", {}, "Contracts"),
            ("POST", f"/contracts/v1/item-upgrades/{PROGRESSION_ID}/{subject}", {}, "OrderID"),
            ("GET", "/agg-stats/v1/stats/v/0", None, "Stats"),
            ("GET", "/v1/customgames", None, "Games"),
            ("GET", f"/v1/parties/{party_id}", None, "Members"),
            ("GET", f"/v1/players/{subject}", None, "CurrentPartyID"),
            ("GET", "/v1/parties/customgameconfigs", None, "CustomGameConfigs"),
            ("POST", f"/v1/parties/{party_id}/balance", {}, "Members"),
            ("POST", f"/v1/parties/{party_id}/invites", {"game_name": "OtherUser", "tag_line": "NA1"}, "InvitationID"),
            ("POST", f"/v1/parties/{party_id}/makecustomgame", {}, "CustomGameData"),
            ("POST", f"/v1/parties/{party_id}/members/{subject}/refreshPlayerIdentity", {}, "Members"),
            ("POST", f"/v1/parties/{party_id}/request", {}, "Members"),
            ("POST", f"/v1/parties/{party_id}/name", {"Name": "Local"}, "Members"),
            ("PUT", f"/v1/parties/{party_id}/accessibility", {"Accessibility": "CLOSED"}, "Members"),
            ("POST", f"/v1/parties/{party_id}/customgame/TeamOne", {"Subject": subject}, "CustomGameData"),
            ("GET", "/matchmaking/v1/queues/configs", None, "Queues"),
            ("GET", "/matchmaking/v1/queues/v/0", None, "Queues"),
            ("PUT", "/name-service/v2/players", [subject], "Players"),
            ("GET", "/player-account/aliases/v1/active", None, "GameName"),
            ("GET", "/player-account/aliases/v1/eligibility", None, "isSuccess"),
            ("POST", "/player-account/aliases/v1/validity", {"game_name": "MatrixUser", "tag_line": "EUW"}, "GameName"),
            ("POST", "/player-reporting/v1/report", {"Subject": subject, "Reason": "test"}, "Success"),
            ("GET", f"/ares-personalization/personalization/v1/players/{subject}/playerloadout", None, "Guns"),
            ("PUT", f"/ares-personalization/personalization/v1/players/{subject}/playerloadout", {"Guns": []}, "Guns"),
            ("GET", f"/entitlements/{ITEM_TYPE_SKIN}/{subject}", None, "Entitlements"),
            ("GET", "/store/v1/offers/", None, "Offers"),
            ("GET", "/cap/v1/wallets", None, "Balances"),
            ("GET", "/cap/v1/orders", None, "Orders"),
            ("POST", "/cap/v1/orders", {"item": ITEM_ID}, "OrderID"),
            ("GET", "/cap/v1/entitlements", None, "Entitlements"),
            ("POST", "/payments/v1/initialize-purchase", {"XID": "x"}, "OrderID"),
            ("GET", "/chat/v1/session", None, "state"),
            ("GET", "/chat/v2/me", None, "Private"),
            ("GET", "/chat/v3/friends", None, "Friends"),
            ("POST", "/chat/v4/friendrequests", {"game_name": "OtherUser", "tag_line": "NA1"}, "Request"),
            ("GET", "/chat/v4/presences", None, "Presences"),
            ("PUT", "/chat/v4/presences", {"state": "chat"}, "Presences"),
            ("GET", "/chat/v5/messages", None, "Messages"),
            ("GET", "/chat/v5/participants", None, "Participants"),
            ("GET", "/chat/v5/conversations", None, "Conversations"),
            ("POST", "/chat/v5/conversations/read", {"Cid": ""}, "Success"),
            ("GET", "/riot-messaging-service/v1/session", None, "state"),
            ("GET", "/riot-messaging-service/v1/out-of-sync", None, "OutOfSync"),
            ("GET", "/riot-messaging-service/v1/message/ares", None, "Messages"),
            ("GET", "/voice-chat/v2/sessions", None, None),
            ("POST", "/voice-chat/v2/sessions", {}, "SessionID"),
            ("DELETE", "/voice-chat/v2/sessions", {}, "SessionID"),
            ("DELETE", "/voice-chat/v2/sessions/voice-test", {}, "Participants"),
            ("GET", "/voice-chat/v2/settings", None, "inputMode"),
            ("GET", "/voice-chat/v2/devices/capture", None, None),
            ("GET", "/voice-chat/v2/devices/render", None, None),
            ("GET", "/voice-chat/v1/audio-properties", None, None),
            ("PUT", "/voice-chat/v1/push-to-talk", {"enabled": True}, "ok"),
            ("GET", "/wegame-integration/v1/player-info", None, "IsUnderage"),
            ("GET", f"/ares-match-details/match-details/v1/matches/{'6ba83249-8544-5b07-bec1-15b91dbdf730'}", None, "MatchInfo"),
        ]

        failures = []
        for method, path, body, required_key in matrix:
            try:
                assert_ok(client.request(method, path, body), method, path, required_key)
            except Exception as exc:
                failures.append((method, path, str(exc)))
        assert not failures, "endpoint failures:\n" + "\n".join(f"{m} {p}: {e}" for m, p, e in failures)

        versioned_queue = assert_ok(client.request("GET", "/matchmaking/v1/queues/custom/release-0.45-shipping-13-404591"), "GET", "/matchmaking/v1/queues/custom/{clientVersion}", "QueueID")
        assert versioned_queue["QueueID"] == "custom", versioned_queue
        assert len(versioned_queue["Queues"]) == 1, versioned_queue

        # Matchmaking-to-core flow at the end so pregame/core endpoints are validated against live state.
        party = assert_ok(client.request("POST", f"/v1/parties/{party_id}/queue", {"QueueID": "v"}), "POST", "/v1/parties/{party_id}/queue", "State")
        assert party["State"] == "MATCHMADE_GAME_STARTING", party
        pregame_player = assert_ok(client.request("GET", f"/pregame/v1/players/{subject}"), "GET", "/pregame/v1/players/{subject}", "MatchID")
        match_id = pregame_player["MatchID"]
        assert_ok(client.request("GET", f"/pregame/v1/matches/{match_id}"), "GET", "/pregame/v1/matches/{matchId}", "PregameState")
        assert_ok(client.request("POST", f"/pregame/v1/matches/{match_id}/lock/{CHARACTER_ID}", {}), "POST", "/pregame/v1/matches/{matchId}/lock/{characterId}", "Players")
        assert_ok(client.request("GET", f"/ares-core-game/v1/matches/{match_id}/allchatmuctoken"), "GET", "/ares-core-game/v1/matches/{matchId}/allchatmuctoken", "Token")
        assert_ok(client.request("POST", f"/ares-core-game/v1/players/{subject}/disassociate/{match_id}", {}), "POST", "/ares-core-game/v1/players/{subject}/disassociate/{matchId}", "ok")
        core = assert_ok(client.request("POST", f"/pregame/v1/matches/{match_id}/start", {}), "POST", "/pregame/v1/matches/{matchId}/start", "ConnectionDetails")
        assert core["ConnectionDetails"]["GameServerPort"] == 7777, core
        assert_ok(client.request("GET", f"/core-game/v1/players/{subject}"), "GET", "/core-game/v1/players/{subject}", "MatchID")
        assert_ok(client.request("GET", f"/core-game/v1/matches/{match_id}"), "GET", "/core-game/v1/matches/{matchId}", "ConnectionDetails")
        print(f"endpoint matrix ok: {len(matrix) + 9} requests")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        out, err = proc.communicate()
        if proc.returncode not in (0, -15, -9, 143, None):
            print(out, file=sys.stderr)
            print(err, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
