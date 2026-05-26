#!/usr/bin/env python3
"""End-to-end HTTP contract smoke test for the local control-plane server.

This intentionally uses only the standard library so it can run on a clean
Windows/Python install before PostgreSQL is configured. It exercises the same
RNet HTTP paths the client calls during account bootstrap, party queueing,
pregame, and core-game handoff.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "Server" / "project_a_server.py"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class Client:
    def __init__(self, base: str, account: str = "Ace#NA1") -> None:
        self.base = base.rstrip("/")
        self.account = account

    def request(self, method: str, path: str, body: object | None = None) -> tuple[int, object]:
        data = None
        headers = {
            "Accept": "application/json",
            "X-Project-A-Account": self.account,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw.decode("utf-8") or "{}") if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            except json.JSONDecodeError:
                parsed = raw.decode("utf-8", "replace")
            return exc.code, parsed


def wait_ready(client: Client) -> None:
    deadline = time.time() + 8
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, payload = client.request("GET", "/process-control/v1/process")
            if status == 200 and isinstance(payload, dict):
                return
        except Exception as exc:  # server not listening yet
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"server did not become ready: {last_error}")


def main() -> int:
    port = free_port()
    log = ROOT / "reverse-logs" / "http_contract_test.jsonl"
    cmd = [
        sys.executable,
        str(SERVER),
        "--port",
        str(port),
        "--log",
        str(log),
        "--allow-memory-db",
        "--account-key",
        "ace-na1",
        "--riot-name",
        "Ace",
        "--tag-line",
        "NA1",
        "--reset-state",
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    client = Client(f"http://127.0.0.1:{port}", "Ace#NA1")
    try:
        wait_ready(client)

        status, account = client.request("GET", "/local/v1/accounts/me")
        assert status == 200, account
        assert account["DisplayName"] == "Ace#NA1", account
        subject = account["Subject"]
        party_id = account["partyId"]

        status, token = client.request("GET", "/rso-auth/v1/authorization/access-token")
        assert status == 200 and token.get("AccessToken"), token
        status, ent = client.request("GET", "/entitlements/v1/token")
        assert status == 200 and ent.get("Token"), ent

        status, player = client.request("GET", f"/parties/v1/players/{subject}")
        assert status == 200 and player["CurrentPartyID"] == party_id, player
        status, party = client.request("GET", f"/parties/v1/parties/{party_id}")
        assert status == 200 and party["ID"] == party_id, party

        status, custom = client.request(
            "POST",
            f"/parties/v1/parties/{party_id}/makecustomgame",
            {
                "name": "Custom Name",
                "description": "Custom Desc",
                "map": "/Game/Maps/Triad/Triad",
                "mode": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
            },
        )
        assert status == 200 and custom["State"] == "CUSTOM_GAME_SETUP", custom
        assert custom["CustomGameData"]["Name"] == "Custom Name", custom
        assert custom["CustomGameData"]["Description"] == "Custom Desc", custom
        assert custom["CustomGameData"]["Settings"]["Map"] == "/Game/Maps/Triad/Triad", custom
        assert custom["CustomGameData"]["Settings"]["GameMode"] == "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C", custom
        status, custom = client.request(
            "POST",
            f"/parties/v1/parties/{party_id}/customgamesettings",
            {
                "CustomGameData": {
                    "Settings": {
                        "Map": "/Game/Maps/Duality/Duality",
                        "GameMode": "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C",
                    }
                }
            },
        )
        assert status == 200, custom
        assert custom["CustomGameData"]["Settings"]["Map"] == "/Game/Maps/Duality/Duality", custom
        assert custom["CustomGameData"]["Settings"]["GameMode"] == "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C", custom
        status, custom = client.request("POST", f"/parties/v1/parties/{party_id}/customgame/TeamTwo", {"PlayerToPutOnTeam": subject})
        assert status == 200 and custom["CustomGameData"]["Membership"]["TeamTwo"], custom

        status, queue = client.request("GET", "/matchmaking/v1/queues/unrated/release-0.45-shipping-13-404591")
        assert status == 200 and queue["QueueID"] == "unrated", queue
        assert len(queue["Queues"]) == 1, queue

        status, queued = client.request("POST", f"/parties/v1/parties/{party_id}/matchmaking/join/unrated", {})
        assert status == 200 and queued["State"] in {"MATCHMADE_GAME_STARTING", "CUSTOM_GAME_STARTING"}, queued
        assert queued["MatchmakingData"]["QueueID"] == "unrated", queued

        status, pre_player = client.request("GET", f"/pregame/v1/players/{subject}")
        assert status == 200 and pre_player["MatchID"], pre_player
        match_id = pre_player["MatchID"]
        status, pre_match = client.request("GET", f"/pregame/v1/matches/{match_id}")
        assert status == 200 and pre_match["ID"] == match_id, pre_match

        character_id = "00000000-0000-0000-0000-000000000123"
        status, locked = client.request("POST", f"/pregame/v1/matches/{match_id}/lock/{character_id}", {})
        assert status == 200 and locked["Players"][0]["CharacterSelectionState"] == "locked", locked

        status, core = client.request("POST", f"/pregame/v1/matches/{match_id}/start", {})
        assert status == 200 and core["ConnectionDetails"]["GameServerPort"] == 7777, core
        status, core_player = client.request("GET", f"/core-game/v1/players/{subject}")
        assert status == 200 and core_player["MatchID"] == match_id, core_player
        status, core_match = client.request("GET", f"/core-game/v1/matches/{match_id}")
        assert status == 200 and core_match["State"] == "IN_PROGRESS", core_match

        status, alias = client.request("PUT", "/player-account/aliases/v1/active", {"GameName": "AceTwo", "TagLine": "NA2"})
        assert status == 200 and alias["DisplayName"] == "AceTwo#NA2", alias

        status, created = client.request("POST", "/local-accounts/v1/accounts", {"GameName": "Friend", "TagLine": "EUW"})
        assert status == 200 and created["Account"]["DisplayName"] == "Friend#EUW", created

        status, names = client.request("PUT", "/name-service/v1/players", {"Subjects": [subject]})
        assert status == 200 and "Players" in names, names

        status, custom = client.request("POST", f"/parties/v1/parties/{party_id}/makecustomgame", {})
        assert status == 200 and custom["State"] == "CUSTOM_GAME_SETUP", custom
        status, custom = client.request("POST", f"/parties/v1/parties/{party_id}/startcustomgame", {})
        assert status == 200 and custom["State"] == "CUSTOM_GAME_STARTING", custom

        status, pre_player = client.request("GET", f"/pregame/v1/players/{subject}")
        assert status == 200 and pre_player["MatchID"], pre_player
        match_id = pre_player["MatchID"]
        jett_id = "add6443a-41bd-e414-f6ad-e58d267f4e95"

        status, selected = client.request("POST", f"/pregame/v1/matches/{match_id}/select/{jett_id}", {})
        assert status == 200 and selected["Players"][0]["CharacterSelectionState"] == "selected", selected

        status, locked = client.request("POST", f"/pregame/v1/matches/{match_id}/lock/{jett_id}", {})
        assert status == 200, locked
        assert locked["Players"][0]["CharacterSelectionState"] == "locked", locked
        assert locked["PregameState"] == "provisioned", locked
        assert locked["ProvisioningFlowID"] == "ShootingRange", locked

        status, heartbeat = client.request("POST", f"/session/v1/sessions/{subject}/heartbeat", {})
        assert status == 200 and heartbeat["LoopState"] == "INGAME", heartbeat

        status, core_player = client.request("GET", f"/core-game/v1/players/{subject}")
        assert status == 200 and core_player["MatchID"] == match_id, core_player
        status, core_match = client.request("GET", f"/core-game/v1/matches/{match_id}")
        assert status == 200 and core_match["State"] == "IN_PROGRESS", core_match
        assert core_match["ProvisioningFlow"] == "ShootingRange", core_match

        status, pre_match = client.request("GET", f"/pregame/v1/matches/{match_id}")
        assert status == 200 and pre_match["PregameState"] == "provisioned", pre_match

        print("http contract ok")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        if proc.returncode not in (0, -15, None):
            out, err = proc.communicate(timeout=1)
            print(out, file=sys.stderr)
            print(err, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
