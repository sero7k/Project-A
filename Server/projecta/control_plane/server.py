"""CLI startup for the Project A control-plane server."""

from __future__ import annotations

import argparse
import os
import ssl
import threading
from pathlib import Path

from .certs import ensure_cert


def main() -> None:
    from . import app as cp

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=39001)
    parser.add_argument("--log", type=Path, default=Path("reverse-logs/rnet_requests.jsonl"))
    parser.add_argument("--cert", type=Path, default=Path("reverse-logs/rnet_probe.crt"))
    parser.add_argument("--key", type=Path, default=Path("reverse-logs/rnet_probe.key"))
    parser.add_argument("--ca-cert", type=Path, default=Path("reverse-logs/rnet_probe_ca.crt"))
    parser.add_argument("--game-host", default="127.0.0.1")
    parser.add_argument("--game-port", type=int, default=7777)
    parser.add_argument("--phase", choices=["menus", "custom", "pregame", "core", "practice"], default="menus")
    parser.add_argument("--database-url", default=os.getenv("PROJECTA_DATABASE_URL") or os.getenv("DATABASE_URL") or cp.DEFAULT_DATABASE_URL)
    parser.add_argument("--allow-memory-db", action="store_true", help="Use in-memory account storage for local smoke tests.")
    parser.add_argument("--no-db-migrate", action="store_true", help="Do not apply Server/sql/schema.sql at startup.")
    parser.add_argument("--reset-state", action="store_true", help="Ignore persisted server_state.game_state for this boot.")
    parser.add_argument("--resume-state", action="store_true", help="Resume the last persisted transient party/match state.")
    parser.add_argument("--account-key", default=os.getenv("PROJECT_A_ACCOUNT_KEY", ""), help="Local account/login key used by the launch scripts. Defaults to a normalized Riot ID when omitted.")
    parser.add_argument("--riot-name", default=os.getenv("PROJECT_A_RIOT_NAME", "DevPlayer"), help="Riot ID game name for the local account.")
    parser.add_argument("--tag-line", default=os.getenv("PROJECT_A_TAG_LINE", "LOCAL"), help="Riot ID tag line for the local account.")
    parser.add_argument("--matchmaking-delay-ms", type=int, default=int(os.getenv("PROJECT_A_MATCHMAKING_DELAY_MS", "0")), help="Delay before local matchmaking advances to pregame; 0 advances immediately.")
    parser.add_argument(
        "--auto-accept-friend-requests",
        action="store_true",
        default=os.getenv("PROJECT_A_AUTO_ACCEPT_FRIEND_REQUESTS") == "1",
        help="Immediately turn local friend requests into friendships after recording the request.",
    )
    args = parser.parse_args()

    if "#" in str(args.riot_name) and (not args.tag_line or args.tag_line == "LOCAL"):
        parsed_name, _, parsed_tag = str(args.riot_name).partition("#")
        if parsed_name:
            args.riot_name = parsed_name
        if parsed_tag:
            args.tag_line = parsed_tag
    if not args.account_key:
        args.account_key = cp.normalize_account_key(f"{args.riot_name}-{args.tag_line}")

    cp.configure_account_store(args.database_url, allow_memory_db=args.allow_memory_db, migrate=not args.no_db_migrate)
    startup_profile = cp.register_local_profile(args.account_key, args.riot_name, args.tag_line)
    cp.set_default_profile_key(startup_profile["key"])
    cp.seed_persisted_profile_defaults(startup_profile)
    ensure_cert(args.cert, args.key, args.ca_cert)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("", encoding="utf-8")

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(args.cert, args.key)

    server = cp.DualProtocolHTTPServer((args.host, args.port), cp.ProbeHandler, tls_context)
    server.default_account_login = startup_profile["key"]
    server.request_log = args.log
    server.log_lock = threading.Lock()
    server.profile_lock = threading.Lock()
    server.ws_lock = threading.Lock()
    server.ws_clients = set()
    server.chat_lock = threading.Lock()
    server.chat_messages = []
    server._ws_id = 1000
    boot_state = cp.initial_game_state(args.game_host, args.game_port, args.phase)
    boot_state["startup_profile_key"] = startup_profile["key"]
    if args.resume_state and not args.reset_state:
        try:
            persisted_state = cp.ACCOUNT_STORE.load_state("game_state", None)
            if isinstance(persisted_state, dict):
                boot_state.update(persisted_state)
        except Exception as exc:
            print(f"warning: failed to load persisted game_state: {exc}", flush=True)
    boot_state["game_host"] = args.game_host
    boot_state["game_port"] = args.game_port
    server.game_state = boot_state
    server.default_account_login = startup_profile["key"]
    server.matchmaking_delay_seconds = max(0.0, float(args.matchmaking_delay_ms) / 1000.0)
    if isinstance(server.game_state.get("chat_messages"), list):
        server.chat_messages = list(server.game_state.get("chat_messages") or [])
    server.seen_profiles = set(server.game_state.get("active_profile_keys") or [])
    server.seen_profiles.add(startup_profile["key"])
    server.game_state["active_profile_keys"] = sorted(server.seen_profiles)
    server.auto_accept_friends = bool(args.auto_accept_friend_requests)

    def next_ws_id() -> int:
        with server.log_lock:
            server._ws_id += 1
            return server._ws_id

    server.next_ws_id = next_ws_id

    def persist_state() -> None:
        try:
            cp.ACCOUNT_STORE.save_state("game_state", server.game_state)
        except Exception as exc:
            print(f"warning: failed to persist game_state: {exc}", flush=True)

    server.persist_state = persist_state
    persist_state()
    print(f"listening on {args.host}:{args.port}; log={args.log}", flush=True)
    server.serve_forever()
