#!/usr/bin/env python3
"""UDP socket observer for game server simulation."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Server"))

from projecta.gameplay.ares import (
    append_packet_handler_marker,
    make_ares_frame,
    make_ares_frame_packet,
    make_ue_stateless_component_payload,
    ue_stateless_component_bit_count,
    prepend_ddos_reserved,
    stateless_candidate_ares_packets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe and optionally reply to game UDP traffic")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--log", default="")
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument(
        "--udp-reply",
        default="none",
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
        ],
    )
    parser.add_argument("--udp-reply-hex", default="")
    parser.add_argument("--stateless-sequence", default="")
    return parser.parse_args()


def _create_ares_empty_packet() -> bytes:
    return append_packet_handler_marker(make_ares_frame(b""))


def _create_stateless_challenge(data: bytes) -> bytes:
    candidates = stateless_candidate_ares_packets(data)
    return candidates[1]["wire_exact_clean_crc"]


def _create_stateless_challenge_exact_clean(data: bytes) -> bytes:
    candidates = stateless_candidate_ares_packets(data)
    return candidates[1]["wire_exact_clean_crc"]


def _create_stateless_challenge_exact_marker(data: bytes) -> bytes:
    candidates = stateless_candidate_ares_packets(data)
    return candidates[1]["wire_exact_marker_crc"]


def _create_bootstrap_response(data: bytes) -> bytes:
    token = data[36:68] if len(data) >= 68 else data
    payload = make_ue_stateless_component_payload(
        handshake_packet=True,
        restart_handshake=False,
        secret_id=False,
        timestamp=0.0,
        cookie=token[:20].ljust(20, b"\x00"),
    )
    return make_ares_frame_packet(payload, ue_stateless_component_bit_count(), crc_includes_marker=False)


def main() -> None:
    args = parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", args.port))
    except OSError as exc:
        print(f"[observer] FAILED to bind UDP port {args.port}: {exc}", file=sys.stderr)
        sys.exit(1)

    sock.settimeout(1.0)
    print(f"[observer] Listening on UDP 0.0.0.0:{args.port}")
    print(f"[observer] Reply mode: {args.udp_reply}")

    start_time = time.time()
    log_file = None
    if args.log:
        log_file = open(args.log, "w", encoding="utf-8")

    try:
        while True:
            if args.seconds > 0 and time.time() - start_time > args.seconds:
                print("[observer] Time limit reached — exiting.")
                break

            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            now = time.time()
            src = f"{addr[0]}:{addr[1]}"
            hexdump = data.hex()
            print(f"[observer] {src}  recv {len(data)} bytes  {hexdump[:64]}{'...' if len(hexdump) > 64 else ''}")

            if log_file:
                json.dump({"timestamp": now, "from": src, "data": hexdump, "length": len(data)}, log_file)
                log_file.write("\n")
                log_file.flush()

            reply: bytes | None = None

            if args.udp_reply == "echo":
                reply = data
            elif args.udp_reply in ("hex", "ares-hex", "packet-hex", "ares-packet-hex"):
                if args.udp_reply_hex:
                    try:
                        reply = bytes.fromhex(args.udp_reply_hex)
                    except ValueError:
                        print("[observer] ERROR: invalid --udp-reply-hex value", file=sys.stderr)
            elif args.udp_reply == "ares-empty-packet":
                reply = _create_ares_empty_packet()
            elif args.udp_reply == "ares-stateless-challenge":
                reply = _create_stateless_challenge(data)
            elif args.udp_reply == "ares-stateless-challenge-exact-clean":
                reply = _create_stateless_challenge_exact_clean(data)
            elif args.udp_reply == "ares-stateless-challenge-exact-marker":
                reply = _create_stateless_challenge_exact_marker(data)
            elif args.udp_reply == "ares-stateless-repeat":
                reply = data
            elif args.udp_reply == "ares-stateless-bootstrap":
                reply = _create_bootstrap_response(data)
            elif args.udp_reply == "ares-stateless-sequence":
                seq = args.stateless_sequence.encode() if args.stateless_sequence else b"\x00" * 8
                payload = seq[:20].ljust(20, b"\x00")
                reply = make_ares_frame_packet(
                    make_ue_stateless_component_payload(handshake_packet=True, restart_handshake=False, secret_id=False, timestamp=0.0, cookie=payload),
                    ue_stateless_component_bit_count(),
                    crc_includes_marker=False,
                )
            elif args.udp_reply == "ares-stateless-burst":
                token = data[:20].ljust(20, b"\x00")
                reply = _create_stateless_challenge(token.ljust(68, b"\x00"))

            if reply:
                try:
                    sock.sendto(reply, addr)
                    print(f"[observer] {src}  sent {len(reply)} bytes  {reply.hex()[:64]}{'...' if len(reply.hex()) > 64 else ''}")
                    if log_file:
                        json.dump({"timestamp": time.time(), "to": src, "data": reply.hex(), "length": len(reply), "mode": args.udp_reply}, log_file)
                        log_file.write("\n")
                        log_file.flush()
                except OSError as exc:
                    print(f"[observer] ERROR sending to {src}: {exc}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\n[observer] Interrupted — shutting down.")
    finally:
        if log_file:
            log_file.close()
        sock.close()
        print("[observer] Socket closed.")


if __name__ == "__main__":
    main()
