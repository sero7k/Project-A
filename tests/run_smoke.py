#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

"""Dependency-free smoke tests for the packaged server."""
import project_a_server as server

server.configure_account_store(allow_memory_db=True)
profile = server.profile_by_key("developer")
assert profile["game_name"] == "DevPlayer"
assert server.wallet_payload(None, profile)["Balances"]
assert server.store_entitlements_payload(server.ITEM_TYPE_PLAYER_CARD, None, profile)["Entitlements"]
loadout = server.ACCOUNT_STORE.get_player_loadout("developer")
assert loadout is not None and loadout.get("Guns")

other = server.profile_by_key("developer2")
request = server.ACCOUNT_STORE.create_friend_request(profile["key"], other["key"])
assert server.ACCOUNT_STORE.accept_friend_request(other["key"], request.request_id) is not None
assert server.ACCOUNT_STORE.friends_for_account(profile["key"])

print("smoke ok")
