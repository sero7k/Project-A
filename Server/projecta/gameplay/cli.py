"""Command-line entrypoint for the game-port observer."""

from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

from .ares import append_packet_handler_marker, make_ares_frame
from .event_log import append_event
from .observers import tcp_observer, udp_observer


def parse_index_sequence(raw: str, *, label: str) -> list[int] | None:
    if not raw:
        return None
    normalized = raw.strip().lower()
    if normalized == "none":
        return []
    if normalized == "all":
        return list(range(87))
    try:
        return [int(value.strip(), 0) for value in raw.split(",") if value.strip()]
    except ValueError as exc:
        raise SystemExit(f"invalid --{label}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument(
        "--udp-reply",
        choices=[
            "none",
            "echo",
            "hex",
            "ares-hex",
            "packet-hex",
            "ares-packet-hex",
            "ares-empty-packet",
            "ares-stateless-challenge",
            "ares-stateless-challenge-exact-clean",
            "ares-stateless-challenge-exact-marker",
            "ares-stateless-repeat",
            "ares-stateless-bootstrap",
            "ares-stateless-sequence",
            "ares-stateless-burst",
            "ares-handshake",
        ],
        default="none",
    )
    parser.add_argument("--udp-reply-hex", default="")
    parser.add_argument("--map", default="/Game/Maps/Poveglia/Range", help="UE4 map URL sent in the Welcome message after handshake completes.")
    parser.add_argument("--game-mode", default="/Script/ShooterGame.ShooterGameMode", help="UE4 GameMode class path for the Welcome message.")
    parser.add_argument("--stateless-sequence", default="")
    parser.add_argument(
        "--handshake-final-sequence",
        default="",
        help="When --udp-reply=ares-handshake, send these final ACK candidate indexes after the client response. Use comma-separated indexes, 'all', or 'none' to wait without a final ACK.",
    )
    args = parser.parse_args()
    try:
        reply_bytes = bytes.fromhex(args.udp_reply_hex) if args.udp_reply_hex else b""
    except ValueError as exc:
        raise SystemExit(f"invalid --udp-reply-hex: {exc}") from exc
    if args.udp_reply in {"hex", "ares-hex", "packet-hex", "ares-packet-hex"} and not reply_bytes:
        raise SystemExit(f"--udp-reply {args.udp_reply} requires --udp-reply-hex")
    if args.udp_reply == "ares-hex":
        reply_bytes = make_ares_frame(reply_bytes)
    elif args.udp_reply == "packet-hex":
        reply_bytes = append_packet_handler_marker(reply_bytes)
    elif args.udp_reply == "ares-packet-hex":
        reply_bytes = append_packet_handler_marker(make_ares_frame(reply_bytes))
    stateless_sequence = parse_index_sequence(args.stateless_sequence, label="stateless-sequence")
    handshake_final_sequence = parse_index_sequence(args.handshake_final_sequence, label="handshake-final-sequence")

    args.log.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    stop = threading.Event()
    append_event(
        args.log,
        lock,
        {
            "event": "observer_start",
            "host": args.host,
            "port": args.port,
            "seconds": args.seconds,
            "udp_reply": args.udp_reply,
            "udp_reply_hex": reply_bytes.hex(),
            "stateless_sequence": stateless_sequence,
            "handshake_final_sequence": handshake_final_sequence,
            "map": args.map,
            "game_mode": args.game_mode,
        },
    )

    game_state = {"map": args.map, "game_mode": args.game_mode, "game_host": args.host, "game_port": args.port}

    threads = [
        threading.Thread(target=udp_observer, args=(args.host, args.port, args.log, lock, stop, args.udp_reply, reply_bytes, stateless_sequence, handshake_final_sequence, game_state), daemon=True),
        threading.Thread(target=tcp_observer, args=(args.host, args.port, args.log, lock, stop), daemon=True),
    ]
    for thread in threads:
        thread.start()

    deadline = time.time() + args.seconds
    try:
        while time.time() < deadline:
            time.sleep(0.25)
    except KeyboardInterrupt:
        append_event(args.log, lock, {"event": "observer_interrupted"})
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2.0)
        append_event(args.log, lock, {"event": "observer_stop"})
    return 0
