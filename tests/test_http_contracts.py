#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.error
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
    log = ARTIFACT_DIR / "http_contracts.jsonl"
    proc = subprocess.Popen([
        sys.executable, str(ROOT / "Server" / "project_a_server.py"),
        "--port", str(port),
        "--log", str(log),
        "--cert", str(ARTIFACT_DIR / "http_contracts.crt"),
        "--key", str(ARTIFACT_DIR / "http_contracts.key"),
        "--ca-cert", str(ARTIFACT_DIR / "http_contracts_ca.crt"),
        "--allow-memory-db",
        "--reset-state",
        "--account-key", "test-user",
        "--riot-name", "TestUser",
        "--tag-line", "EUW",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def request(method: str, path: str, body=None, account: str = "test-user"):
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

        status, account = request("GET", "/local/v1/account")
        assert status == 200 and account["DisplayName"] == "TestUser#EUW", account
        subject = account["Subject"]
        party_id = account["partyId"]

        checks = [
            ("GET", "/rso-auth/v1/authorization/access-token", None, "AccessToken"),
            ("GET", "/entitlements/v1/token", None, "Token"),
            ("GET", "/riotclient/region-locale", None, "region"),
            ("GET", "/v1/config/na", None, "Collapsed"),
            ("GET", "/content-service/v2/content", None, "Characters"),
            ("GET", "/contract-definitions/v2/definitions", None, "ContractDefinitions"),
            ("GET", f"/contracts/v1/contracts/{subject}", None, "Contracts"),
            ("GET", "/matchmaking/v1/queues/configs", None, "Queues"),
            ("GET", f"/parties/v1/players/{subject}", None, "CurrentPartyID"),
            ("GET", f"/parties/v1/parties/{party_id}", None, "EligibleQueues"),
            ("GET", f"/personalization/v1/players/{subject}/playerloadout", None, "Guns"),
            ("GET", f"/store/v1/wallet/{subject}", None, "Balances"),
            ("GET", "/cap/v1/entitlements", None, "Entitlements"),
            ("GET", "/chat/v1/session", None, "state"),
            ("GET", "/chat/v2/me", None, "Private"),
            ("GET", "/chat/v3/friends", None, "Friends"),
            ("GET", "/voice-chat/v2/sessions", None, None),
            ("GET", "/wegame-integration/v1/player-info", None, None),
        ]
        for method, path, body, required_key in checks:
            status, payload = request(method, path, body)
            assert status == 200, (method, path, status, payload)
            if required_key:
                assert isinstance(payload, dict) and required_key in payload, (method, path, required_key, payload)

        status, loadout = request("GET", f"/personalization/v1/players/{subject}/playerloadout")
        assert status == 200 and loadout["Guns"], loadout
        status, skins = request("GET", f"/entitlements/e7c63390-eda7-46e0-bb7a-a6abdacd2433/{subject}")
        assert status == 200 and skins["Entitlements"], skins

        status, created = request("POST", "/local/v1/accounts", {"account_key": "other", "game_name": "Other", "tag_line": "NA1"})
        assert status == 201 and created["DisplayName"] == "Other#NA1", created

        status, party = request("POST", f"/parties/v1/parties/{party_id}/queue", {"QueueID": "v"})
        assert status == 200 and party["State"] == "MATCHMADE_GAME_STARTING", party
        status, pregame_player = request("GET", f"/pregame/v1/players/{subject}")
        assert status == 200 and pregame_player["MatchID"], pregame_player
        match_id = pregame_player["MatchID"]
        status, match = request("GET", f"/pregame/v1/matches/{match_id}")
        assert status == 200 and match["PregameState"] in {"character_select_active", "character_select_finished"}, match
        status, lock = request("POST", f"/pregame/v1/matches/{match_id}/lock/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", {})
        assert status == 200 and lock["Players"][0]["CharacterSelectionState"] == "locked", lock
        status, core = request("POST", f"/pregame/v1/matches/{match_id}/start", {})
        assert status == 200 and core["ConnectionDetails"]["GameServerPort"] == 7777, core
        status, core_player = request("GET", f"/core-game/v1/players/{subject}")
        assert status == 200 and core_player["MatchID"] == match_id, core_player
        print("http contract smoke ok")
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
