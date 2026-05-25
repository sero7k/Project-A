from __future__ import annotations

import base64
import http.client
import json
import ssl
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Server import project_a_server as server


def reset_memory_store() -> None:
    server.configure_account_store(allow_memory_db=True)


def test_accounts_have_names_and_distinct_default_parties() -> None:
    reset_memory_store()
    first = server.profile_by_key("developer")
    second = server.profile_by_key("developer2")

    assert first["game_name"] == "DevPlayer"
    assert first["tag_line"] == "LOCAL"
    assert second["game_name"] == "DevPlayer2"
    assert second["tag_line"] == "LOCAL2"
    assert server.party_id_for_profile(first) != server.party_id_for_profile(second)


def test_default_party_payload_only_contains_current_account() -> None:
    reset_memory_store()
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")
    first = server.profile_by_key("developer")
    second = server.profile_by_key("developer2")

    first_party = server.party_payload(game_state, profile=first)
    second_party = server.party_payload(game_state, profile=second)

    assert [member["Subject"] for member in first_party["Members"]] == [first["subject"]]
    assert [member["Subject"] for member in second_party["Members"]] == [second["subject"]]
    assert first_party["ID"] != second_party["ID"]
    assert first_party["MUCName"] != second_party["MUCName"]
    assert first_party["VoiceRoomID"] != second_party["VoiceRoomID"]


def test_chat_participants_follow_party_membership() -> None:
    reset_memory_store()
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")
    first = server.profile_by_key("developer")
    second = server.profile_by_key("developer2")
    first_room = server.party_muc_name(server.party_id_for_profile(first))
    second_room = server.party_muc_name(server.party_id_for_profile(second))
    server.join_chat_room(game_state, first_room, first)
    server.join_chat_room(game_state, second_room, second)

    first_participants = server.chat_participants_payload(game_state, first_room, first)["Participants"]
    second_participants = server.chat_participants_payload(game_state, second_room, second)["Participants"]

    assert [participant["Subject"] for participant in first_participants] == [first["subject"]]
    assert [participant["Subject"] for participant in second_participants] == [second["subject"]]


def test_explicit_join_is_required_to_share_party() -> None:
    reset_memory_store()
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")
    first = server.profile_by_key("developer")
    second = server.profile_by_key("developer2")
    first_party_id = server.party_id_for_profile(first)

    assert server.party_id_for_profile(second) != first_party_id
    server.ACCOUNT_STORE.join_party(second["key"], first_party_id)

    shared_party = server.party_payload(game_state, first_party_id, first)
    subjects = {member["Subject"] for member in shared_party["Members"]}
    assert subjects == {first["subject"], second["subject"]}


def basic_auth(token: str) -> str:
    raw = base64.b64encode(f"riot:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {raw}"


def start_http_server() -> tuple[server.DualProtocolHTTPServer, threading.Thread]:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    httpd = server.DualProtocolHTTPServer(("127.0.0.1", 0), server.ProbeHandler, ctx)
    httpd.request_log = Path("NUL")
    httpd.log_lock = threading.Lock()
    httpd.profile_lock = threading.Lock()
    httpd.ws_lock = threading.Lock()
    httpd.ws_clients = set()
    httpd.chat_lock = threading.Lock()
    httpd.chat_messages = []
    httpd._ws_id = 1000
    httpd.game_state = server.initial_game_state("127.0.0.1", 7777, "menus")
    httpd.seen_profiles = set()
    httpd.next_ws_id = lambda: 1001
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def request_json(port: int, path: str, token: str) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers={"Authorization": basic_auth(token)})
    response = conn.getresponse()
    body = response.read()
    conn.close()
    assert response.status == 200, body
    return json.loads(body.decode("utf-8"))


def test_http_two_clients_are_not_forced_into_one_party() -> None:
    reset_memory_store()
    httpd, thread = start_http_server()
    try:
        port = int(httpd.server_address[1])
        first_player = request_json(port, "/parties/v1/players/current", "developer")
        second_player = request_json(port, "/parties/v1/players/current", "developer2")
        assert first_player["CurrentPartyID"] != second_player["CurrentPartyID"]

        first_party = request_json(port, f"/parties/v1/parties/{first_player['CurrentPartyID']}", "developer")
        second_party = request_json(port, f"/parties/v1/parties/{second_player['CurrentPartyID']}", "developer2")

        assert [member["Subject"] for member in first_party["Members"]] == [first_player["Subject"]]
        assert [member["Subject"] for member in second_party["Members"]] == [second_player["Subject"]]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
