#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "reverse-logs" / "test-artifacts"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    port = free_port()
    log = ARTIFACT_DIR / "full_api_surface.jsonl"
    proc = subprocess.Popen([
        sys.executable, str(ROOT / "Server" / "project_a_server.py"),
        "--port", str(port),
        "--log", str(log),
        "--cert", str(ARTIFACT_DIR / "full_api_surface.crt"),
        "--key", str(ARTIFACT_DIR / "full_api_surface.key"),
        "--ca-cert", str(ARTIFACT_DIR / "full_api_surface_ca.crt"),
        "--allow-memory-db",
        "--reset-state",
        "--account-key", "surface-user",
        "--riot-name", "SurfaceUser",
        "--tag-line", "QA1",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def request(method: str, path: str, body=None, account: str = "surface-user"):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["content-type"] = "application/json"
        token = base64.b64encode(f"riot:{account}".encode("utf-8")).decode("ascii")
        headers["authorization"] = "Basic " + token
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            parsed = json.loads(raw) if raw else None
            return resp.status, parsed

    def expect(method: str, path: str, body=None, key: str | None = None):
        status, payload = request(method, path, body)
        assert 200 <= status < 300, (method, path, status, payload)
        if key is not None:
            assert isinstance(payload, dict) and key in payload, (method, path, key, payload)
        return payload

    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise RuntimeError(f"server exited early\nSTDOUT={out}\nSTDERR={err}")
            try:
                request("GET", "/process-control/v1/process")
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not accept HTTP connections")

        account = expect("GET", "/local/v1/account", key="Subject")
        subject = account["Subject"]
        party_id = account["partyId"]
        party_muc = f"ares-party-{party_id}@conference.pvp.net"
        character_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        contract_id = "90a1aaa8-f6dc-42f7-ae65-181c9fd0d80b"
        item_progression_id = "d91fb318-4e40-b4c9-8c0b-bb9da28bac55"
        player_card_type = "bcef87d6-209b-46c6-8b19-fbe40bd95abc"
        skin_type = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"

        # Bootstrap/local/auth/config/legal/anti-addiction/product integration.
        expect("GET", "/process-control/v1/process", key="isRunning")
        expect("PUT", "/riotclient/region-locale", {"region": "na", "locale": "en_US"}, key="region")
        expect("GET", "/rso-auth/v1/authorization/access-token", key="AccessToken")
        expect("GET", "/entitlements/v1/token", key="Token")
        expect("GET", "/metadata/v1", key="ClientVersion")
        expect("GET", "/anti-addiction/v1/products/ares/policies/playtime/anti-addiction-state", key="canPlay")
        expect("GET", "/anti-addiction/v1/products/ares/policies/shutdown/anti-addiction-state", key="canPlay")
        expect("GET", "/anti-addiction/v1/products/ares/policies/warningMessage/anti-addiction-state", key="canPlay")
        expect("GET", "/eula/v1/agreement/content", key="content")
        expect("GET", "/eula/v1/privacy-policy/content", key="content")
        expect("POST", "/product-integration/v1/app-repair/apply", {"RepairCode": "none"}, key="Success")
        expect("GET", "/v1/config/na", key="Collapsed")
        expect("GET", "/latency/v1/ingest", key="Success")

        # Content/contracts/store/account-owned data.
        expect("GET", "/content-service/v2/content", key="Characters")
        expect("GET", "/contract-definitions/v2/definitions/story", key="ContractDefinitions")
        expect("GET", "/contract-definitions/v2/definitions", key="ContractDefinitions")
        expect("GET", "/contract-definitions/v2/item-upgrades", key="ItemUpgrades")
        expect("GET", f"/contracts/v1/contracts/{subject}", key="Contracts")
        expect("POST", f"/contracts/v1/contracts/{subject}/special/{contract_id}", {}, key="Contracts")
        expect("POST", f"/contracts/v1/item-upgrades/{item_progression_id}/{subject}", {}, key="OrderID")
        expect("GET", f"/agg-stats/v1/stats/v/0", key="Stats")
        expect("GET", f"/personalization/v1/players/{subject}/playerloadout", key="Guns")
        expect("PUT", f"/ares-personalization/personalization/v1/players/{subject}/playerloadout", {"Subject": subject, "Guns": []}, key="Guns")
        expect("GET", f"/entitlements/{player_card_type}/{subject}", key="Entitlements")
        expect("GET", f"/entitlements/{skin_type}/{subject}", key="Entitlements")
        expect("GET", "/store/v1/offers/", key="Offers")
        expect("GET", f"/store/v1/wallet/{subject}", key="Balances")
        expect("GET", "/cap/v1/wallets", key="Balances")
        expect("GET", "/cap/v1/entitlements", key="Entitlements")
        expect("POST", "/cap/v1/orders", {"ItemID": player_card_type}, key="OrderID")
        expect("POST", "/payments/v1/initialize-purchase", {"Session": "local"}, key="OrderID")

        # Account alias/name-service/reporting.
        expect("GET", "/player-account/aliases/v1/active", key="DisplayName")
        expect("GET", "/player-account/aliases/v1/eligibility", key="isSuccess")
        expect("POST", "/player-account/aliases/v1/validity", {"game_name": "SurfaceUser", "tag_line": "QA1"}, key="isSuccess")
        expect("POST", "/player-account/aliases/v1/aliases", {"game_name": "SurfaceUser", "tag_line": "QA1"}, key="DisplayName")
        expect("PUT", "/name-service/v2/players", [subject], key="Players")
        expect("POST", "/player-reporting/v1/report", {"Offender_puuid": subject, "Categories": []}, key="Token")
        expect("GET", "/wegame-integration/v1/player-info", key="IsUnderage")

        # Party/social/custom-game/matchmaking.
        expect("GET", "/v1/customgames", key="Games")
        expect("GET", f"/v1/players/{subject}", key="CurrentPartyID")
        expect("GET", f"/v1/parties/{party_id}", key="Members")
        expect("GET", "/v1/parties/customgameconfigs", key="CustomGameConfigs")
        expect("POST", f"/v1/parties/{party_id}/balance", {}, key="Members")
        expect("POST", f"/v1/parties/{party_id}/makecustomgame", {}, key="State")
        expect("POST", f"/v1/parties/{party_id}/members/{subject}/refreshPlayerIdentity", {}, key="Members")
        expect("POST", f"/v1/parties/{party_id}/request", {}, key="Members")
        expect("POST", f"/v1/parties/{party_id}/name", {"Name": "Local"}, key="Members")
        expect("PUT", f"/v1/parties/{party_id}/accessibility", {"Accessibility": "CLOSED"}, key="Members")
        expect("POST", f"/v1/parties/{party_id}/customgame/TeamOne", {"PlayerToPutOnTeam": subject}, key="Members")
        expect("GET", "/matchmaking/v1/queues/configs", key="Queues")
        expect("GET", "/matchmaking/v1/queues/v/status", key="Queues")
        party = expect("POST", f"/v1/parties/{party_id}/queue", {"QueueID": "v"}, key="State")
        assert party["State"] in {"MATCHMAKING", "MATCHMADE_GAME_STARTING"}, party

        # Pregame then core-game transition.
        pregame_player = expect("GET", f"/pregame/v1/players/{subject}", key="MatchID")
        match_id = pregame_player["MatchID"]
        assert match_id, pregame_player
        expect("GET", f"/pregame/v1/matches/{match_id}", key="PregameState")
        expect("GET", f"/pregame/v1/matches/{match_id}/chattoken", key="Token")
        expect("GET", f"/pregame/v1/matches/{match_id}/teamvoicetoken", key="Token")
        expect("POST", f"/pregame/v1/matches/{match_id}/lock/{character_id}", {}, key="Players")
        core = expect("POST", f"/pregame/v1/matches/{match_id}/start", {}, key="ConnectionDetails")
        assert core["ConnectionDetails"]["GameServerPort"] == 7777, core
        expect("GET", f"/ares-core-game/v1/matches/{match_id}/allchatmuctoken", key="Token")
        expect("GET", f"/core-game/v1/matches/{match_id}/teamchatmuctoken", key="Token")
        expect("POST", f"/ares-core-game/v1/players/{subject}/disassociate/{match_id}", {}, key="ok")
        expect("GET", f"/core-game/v1/players/{subject}", key="MatchID")
        expect("GET", f"/core-game/v1/matches/{match_id}", key="ConnectionDetails")
        expect("GET", f"/ares-match-details/match-details/v1/matches/{match_id}", key="MatchInfo")

        # Chat, friends, RMS, voice.
        expect("GET", "/chat/v1/session", key="state")
        expect("PUT", "/chat/v2/me", {"state": "chat", "msg": ""}, key="Private")
        expect("GET", "/chat/v3/friends", key="Friends")
        expect("GET", "/chat/v4/friendrequests", key="Requests")
        expect("GET", "/chat/v4/presences", key="Presences")
        expect("POST", "/chat/v5/conversations", {"Cid": party_muc}, key="Cid")
        expect("GET", "/chat/v5/conversations", key="Conversations")
        expect("GET", "/chat/v5/participants", key="Participants")
        expect("POST", "/chat/v5/messages", {"cid": party_muc, "message": "hello"}, key="Message")
        expect("GET", f"/chat/v5/conversations/{urllib.parse.quote(party_muc, safe='')}/messages", key="Messages")
        expect("POST", "/chat/v5/conversations/read", {"Cid": party_muc}, key="Success")
        expect("GET", "/riot-messaging-service/v1/session", key="state")
        expect("GET", "/riot-messaging-service/v1/out-of-sync", key="OutOfSync")
        expect("GET", "/riot-messaging-service/v1/message/test", key="Messages")
        expect("GET", "/voice-chat/v2/sessions")
        expect("POST", "/voice-chat/v2/sessions", {}, key="SessionID")
        expect("DELETE", "/voice-chat/v2/sessions", {}, key="SessionID")
        expect("DELETE", "/voice-chat/v2/sessions/local", {}, key="Participants")
        expect("GET", "/voice-chat/v2/settings", key="inputMode")
        expect("GET", "/voice-chat/v2/devices/capture")
        expect("GET", "/voice-chat/v2/devices/render")
        expect("PUT", "/voice-chat/v1/audio-properties", {}, key=None)
        expect("PUT", "/voice-chat/v1/push-to-talk", {}, key="ok")

        print("full api surface smoke ok")
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
