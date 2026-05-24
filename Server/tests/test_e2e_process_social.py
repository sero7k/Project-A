from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def basic_auth(token: str) -> str:
    raw = base64.b64encode(f"riot:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {raw}"


def request_json(port: int, path: str, token: str, method: str = "GET", body: dict | None = None, expected_status: int = 200) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw_body = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": basic_auth(token)}
    if raw_body is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=raw_body, headers=headers)
    response = conn.getresponse()
    response_body = response.read()
    conn.close()
    assert response.status == expected_status, response_body
    return json.loads(response_body.decode("utf-8"))


@pytest.fixture()
def server_process(tmp_path: Path):
    port = free_port()
    database_url = os.getenv("PROJECTA_E2E_DATABASE_URL")
    args = [
        sys.executable,
        str(SERVER_ROOT / "project_a_server.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log",
        str(tmp_path / "requests.jsonl"),
        "--cert",
        str(tmp_path / "server.crt"),
        "--key",
        str(tmp_path / "server.key"),
        "--ca-cert",
        str(tmp_path / "ca.crt"),
    ]
    if database_url:
        args.extend(["--database-url", database_url])
    else:
        args.append("--allow-memory-db")

    proc = subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=5)
            raise AssertionError(f"server exited early with {proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        try:
            request_json(port, "/system/v1/builds", "healthcheck")
            break
        except (ConnectionRefusedError, TimeoutError, OSError, AssertionError):
            time.sleep(0.2)
    else:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        raise AssertionError(f"server did not become ready\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

    try:
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_full_social_invite_and_party_chat_e2e(server_process: int) -> None:
    port = server_process
    unique = uuid.uuid4().hex[:8]
    alice_token = f"e2ealice{unique}"
    bob_token = f"e2ebob{unique}"
    bob_name = f"Sero{unique[:4]}"
    bob_tag = unique[-5:].upper()

    alice_player = request_json(port, "/parties/v1/players/current", alice_token)
    bob_player = request_json(port, "/parties/v1/players/current", bob_token)
    assert alice_player["CurrentPartyID"] != bob_player["CurrentPartyID"]

    updated_alias = request_json(
        port,
        "/player-account/aliases/v1/active",
        bob_token,
        method="POST",
        body={"game_name": bob_name, "tag_line": bob_tag},
    )
    assert updated_alias["GameName"] == bob_name
    assert updated_alias["TagLine"] == bob_tag
    assert updated_alias["DisplayName"] == f"{bob_name}#{bob_tag}"

    alice_friends = request_json(port, "/friends/v1/friends", alice_token)["Friends"]
    assert all(friend["Subject"] != alice_player["Subject"] for friend in alice_friends)
    bob_friend = next(friend for friend in alice_friends if friend["Subject"] == bob_player["Subject"])
    assert bob_friend["GameName"] == bob_name
    assert bob_friend["TagLine"] == bob_tag
    assert bob_friend["Presence"]["online"] is True
    assert bob_friend["Presence"]["availability"] == "online"

    alice_party_before = request_json(port, f"/parties/v1/parties/{alice_player['CurrentPartyID']}", alice_token)
    assert [member["Subject"] for member in alice_party_before["Members"]] == [alice_player["Subject"]]

    invite = request_json(
        port,
        f"/parties/v1/parties/{alice_player['CurrentPartyID']}/invites/name/{quote(bob_name)}/tag/{quote(bob_tag)}",
        alice_token,
        method="POST",
    )
    assert invite["PartyID"] == alice_player["CurrentPartyID"]
    assert invite["Subject"] == bob_player["Subject"]

    bob_invites = request_json(port, f"/parties/v1/players/{bob_player['Subject']}/invites", bob_token)["Invites"]
    assert any(item["ID"] == invite["ID"] for item in bob_invites)

    joined_party = request_json(
        port,
        f"/parties/v1/parties/{alice_player['CurrentPartyID']}/invites/{invite['ID']}/accept",
        bob_token,
        method="POST",
    )
    assert {member["Subject"] for member in joined_party["Members"]} == {alice_player["Subject"], bob_player["Subject"]}

    room = joined_party["MUCName"]
    request_json(port, "/chat/v5/conversations", alice_token, method="POST", body={"cid": room})
    request_json(port, "/chat/v5/conversations", bob_token, method="POST", body={"cid": room})

    alice_message = request_json(port, "/chat/v5/messages", alice_token, method="POST", body={"cid": room, "message": "hello from alice"})
    bob_message = request_json(port, "/chat/v5/messages", bob_token, method="POST", body={"cid": room, "message": "hello from bob"})
    history = request_json(port, f"/chat/v5/messages?cid={quote(room, safe='')}", alice_token)["Messages"]

    assert alice_message["Body"] == "hello from alice"
    assert bob_message["Body"] == "hello from bob"
    assert any(message["Body"] == "hello from alice" and message["Subject"] == alice_player["Subject"] for message in history)
    assert any(message["Body"] == "hello from bob" and message["Subject"] == bob_player["Subject"] for message in history)
