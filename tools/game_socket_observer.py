#!/usr/bin/env python3
"""UDP socket observer for game server simulation."""

import argparse
import socket
import sys
import time
import json
import struct


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe and optionally reply to game UDP traffic")
    parser.add_argument("--port", type=int, default=7777, help="UDP port to listen on")
    parser.add_argument("--log", default="", help="JSONL log file path")
    parser.add_argument("--seconds", type=int, default=0, help="Run for N seconds (0=forever)")
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
        help="Reply mode",
    )
    parser.add_argument("--udp-reply-hex", default="", help="Hex payload to send back (for hex/ares-hex modes)")
    parser.add_argument("--stateless-sequence", default="", help="Sequence string for stateless-sequence mode")
    return parser.parse_args()


def create_ares_empty_packet() -> bytes:
    """Minimal Ares-style empty packet — just enough header to not be rejected immediately."""
    # Ares packets often start with a 4-byte magic followed by packet type.
    # This is a best-guess placeholder based on common UE4 networking patterns.
    magic = struct.pack("<I", 0x9E2A83C1)  # UE4 packet magic (little-endian)
    packet_type = b"\x00"  # NMT_Hello or similar
    return magic + packet_type


def create_stateless_challenge_response(data: bytes) -> bytes:
    """Generate a minimal stateless challenge reply.

    Stateless challenge protocols typically expect the server to echo back
    a client-provided nonce with some server-side wrapper. Without exact
    format knowledge, we echo the first 4 bytes prefixed by a simple
    header so the client sees *something* it might accept.
    """
    if len(data) >= 4:
        nonce = data[:4]
    else:
        nonce = data.ljust(4, b"\x00")
    # Prefix with what looks like a tiny packet header (magic + type)
    header = struct.pack("<I", 0x9E2A83C1) + b"\x01"
    return header + nonce


def create_bootstrap_response(data: bytes) -> bytes:
    """Minimal bootstrap reply for ares-stateless-bootstrap mode."""
    header = struct.pack("<I", 0x9E2A83C1) + b"\x02"
    if len(data) >= 8:
        return header + data[:8]
    return header + data.ljust(8, b"\x00")


def main() -> None:
    args = parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", args.port))
    except OSError as exc:
        print(f"[observer] FAILED to bind to UDP port {args.port}: {exc}", file=sys.stderr)
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
                json.dump(
                    {
                        "timestamp": now,
                        "from": src,
                        "data": hexdump,
                        "length": len(data),
                    },
                    log_file,
                )
                log_file.write("\n")
                log_file.flush()

            # ---- reply logic -------------------------------------------------
            reply: bytes | None = None

            if args.udp_reply == "echo":
                reply = data

            elif args.udp_reply in ("hex", "ares-hex", "packet-hex", "ares-packet-hex"):
                if args.udp_reply_hex:
                    try:
                        reply = bytes.fromhex(args.udp_reply_hex)
                    except ValueError:
                        print(f"[observer] ERROR: invalid --udp-reply-hex value", file=sys.stderr)

            elif args.udp_reply == "ares-empty-packet":
                reply = create_ares_empty_packet()

            elif args.udp_reply == "ares-stateless-challenge":
                reply = create_stateless_challenge_response(data)

            elif args.udp_reply in (
                "ares-stateless-challenge-exact-clean",
                "ares-stateless-challenge-exact-marker",
            ):
                # Same as basic challenge for now; exact-clean/marker differ
                # only in trailing bytes, which we don't know yet.
                reply = create_stateless_challenge_response(data)

            elif args.udp_reply == "ares-stateless-repeat":
                reply = data  # identical to echo

            elif args.udp_reply == "ares-stateless-bootstrap":
                reply = create_bootstrap_response(data)

            elif args.udp_reply == "ares-stateless-sequence":
                seq = args.stateless_sequence.encode() if args.stateless_sequence else b"\x00" * 8
                header = struct.pack("<I", 0x9E2A83C1) + b"\x03"
                reply = header + seq[:16].ljust(16, b"\x00")

            elif args.udp_reply == "ares-stateless-burst":
                # Send back the first chunk of data with a small header
                header = struct.pack("<I", 0x9E2A83C1) + b"\x04"
                reply = header + data[:32]

            # -----------------------------------------------------------------

            if reply:
                try:
                    sock.sendto(reply, addr)
                    print(f"[observer] {src}  sent {len(reply)} bytes  {reply.hex()[:64]}{'...' if len(reply.hex()) > 64 else ''}")
                    if log_file:
                        json.dump(
                            {
                                "timestamp": time.time(),
                                "to": src,
                                "data": reply.hex(),
                                "length": len(reply),
                                "mode": args.udp_reply,
                            },
                            log_file,
                        )
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
