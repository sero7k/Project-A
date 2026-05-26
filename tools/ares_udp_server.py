#!/usr/bin/env python3
"""Minimal local Ares/UE4 UDP endpoint for Project A.

This is not a full game server yet. It implements the UE4.22 stateless
connect handshake used before the control channel starts, then logs every
packet so the next protocol layer can be reconstructed from real traffic.
"""

from __future__ import annotations

import argparse
import binascii
import json
import os
import secrets
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path


HANDSHAKE_PACKET_BITS = 195
RESTART_RESPONSE_BITS = 355
COOKIE_BYTES = 20


def ue_mem_crc32(data: bytes, seed: int = 0) -> int:
    return binascii.crc32(data, seed ^ 0xFFFFFFFF) ^ 0xFFFFFFFF


class BitStream:
    def __init__(self, data: bytes = b"") -> None:
        self.data = bytearray(data)
        self.bitpos = 0

    def bits_left(self) -> int:
        return len(self.data) * 8 - self.bitpos

    def read_bit(self) -> int:
        if self.bitpos >= len(self.data) * 8:
            raise ValueError("read past end")
        value = (self.data[self.bitpos >> 3] >> (self.bitpos & 7)) & 1
        self.bitpos += 1
        return value

    def read_u8_from_bit(self) -> int:
        return self.read_bit()

    def read_bytes(self, count: int) -> bytes:
        out = bytearray()
        for _ in range(count):
            value = 0
            for bit in range(8):
                value |= self.read_bit() << bit
            out.append(value)
        return bytes(out)

    def read_float(self) -> float:
        return struct.unpack("<f", self.read_bytes(4))[0]


class BitWriter:
    def __init__(self) -> None:
        self.data = bytearray()
        self.bitpos = 0

    def write_bit(self, value: int) -> None:
        if self.bitpos == len(self.data) * 8:
            self.data.append(0)
        if value & 1:
            self.data[self.bitpos >> 3] |= 1 << (self.bitpos & 7)
        self.bitpos += 1

    def write_bytes(self, data: bytes) -> None:
        for byte in data:
            for bit in range(8):
                self.write_bit((byte >> bit) & 1)

    def write_float(self, value: float) -> None:
        self.write_bytes(struct.pack("<f", value))

    def finish_with_termination(self) -> bytes:
        self.write_bit(1)
        return bytes(self.data)


@dataclass
class ClientState:
    challenge_cookie: bytes = field(default_factory=lambda: b"\x00" * COOKIE_BYTES)
    challenge_timestamp: float = 0.0
    connected: bool = False
    last_seen: float = 0.0
    packets_in: int = 0
    packets_out: int = 0


class AresUdpServer:
    def __init__(self, host: str, port: int, log_path: Path | None) -> None:
        self.host = host
        self.port = port
        self.log_path = log_path
        self.clients: dict[tuple[str, int], ClientState] = {}
        self.started_at = time.monotonic()
        self.log_file = None

    def server_time(self) -> float:
        return float(time.monotonic() - self.started_at + 1.0)

    def log_event(self, event: str, **fields: object) -> None:
        record = {"ts": time.time(), "event": event, **fields}
        line = json.dumps(record, separators=(",", ":"))
        print(line, flush=True)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def build_handshake_packet(self, timestamp: float, cookie: bytes, secret_id: int = 0) -> bytes:
        writer = BitWriter()
        writer.write_bit(1)          # HandshakeBit
        writer.write_bit(0)          # RestartHandshakeBit
        writer.write_bit(secret_id)  # SecretIdBit
        writer.write_float(timestamp)
        writer.write_bytes(cookie[:COOKIE_BYTES].ljust(COOKIE_BYTES, b"\x00"))
        return writer.finish_with_termination()

    def build_restart_request(self) -> bytes:
        writer = BitWriter()
        writer.write_bit(1)
        writer.write_bit(1)
        return writer.finish_with_termination()

    def build_ares_envelope(self, payload: bytes) -> bytes:
        crc = ue_mem_crc32(payload) & 0xFFFFFFFF
        return struct.pack("<IH", crc, len(payload)) + payload

    def parse_handshake(self, payload: bytes) -> dict[str, object] | None:
        bits = BitStream(payload)
        try:
            if bits.read_bit() != 1:
                return {"handshake": False}

            remaining = bits.bits_left()
            expected = HANDSHAKE_PACKET_BITS - 1
            restart_expected = RESTART_RESPONSE_BITS - 1
            # UDP gives whole bytes, while UE's PacketHandler tracks exact bit counts.
            # The 196-bit handshake appears on the wire as 25 bytes, leaving 199 bits
            # after the first handshake bit. Accept the byte-rounded forms and ignore
            # the trailing zero padding after the termination bit.
            rounded_expected = ((HANDSHAKE_PACKET_BITS + 7) // 8) * 8 - 1
            rounded_restart_expected = ((RESTART_RESPONSE_BITS + 7) // 8) * 8 - 1
            if remaining not in {expected, restart_expected, rounded_expected, rounded_restart_expected}:
                return {"handshake": True, "valid": False, "bits_left": remaining}

            restart = bool(bits.read_bit())
            secret_id = bits.read_u8_from_bit()
            timestamp = bits.read_float()
            cookie = bits.read_bytes(COOKIE_BYTES)
            orig_cookie = b""
            if remaining in {restart_expected, rounded_restart_expected}:
                orig_cookie = bits.read_bytes(COOKIE_BYTES)

            return {
                "handshake": True,
                "valid": True,
                "restart": restart,
                "secret_id": secret_id,
                "timestamp": timestamp,
                "cookie": cookie,
                "orig_cookie": orig_cookie,
            }
        except ValueError as exc:
            return {"handshake": True, "valid": False, "error": str(exc)}

    def handle_packet(self, sock: socket.socket, payload: bytes, addr: tuple[str, int]) -> None:
        state = self.clients.setdefault(addr, ClientState())
        state.last_seen = time.time()
        state.packets_in += 1
        parsed = self.parse_handshake(payload)

        self.log_event(
            "recv",
            addr=f"{addr[0]}:{addr[1]}",
            length=len(payload),
            hex=payload.hex(),
            parsed=self._json_safe_parsed(parsed),
        )

        reply = None
        mode = "none"

        if parsed and parsed.get("handshake") is True and parsed.get("valid") is True:
            timestamp = float(parsed.get("timestamp") or 0.0)
            cookie = parsed.get("cookie")
            if not isinstance(cookie, bytes):
                cookie = b"\x00" * COOKIE_BYTES

            if timestamp == 0.0:
                state.challenge_timestamp = self.server_time()
                state.challenge_cookie = secrets.token_bytes(COOKIE_BYTES)
                reply = self.build_handshake_packet(state.challenge_timestamp, state.challenge_cookie)
                mode = "challenge"
            else:
                # UE clients accept the ack cookie and derive initial packet sequence from it.
                # Echoing the client's cookie is enough to move the PacketHandler to initialized.
                state.connected = True
                state.challenge_cookie = cookie
                reply = self.build_handshake_packet(-1.0, cookie)
                mode = "ack"
        elif parsed and parsed.get("handshake") is False:
            state.challenge_timestamp = self.server_time()
            state.challenge_cookie = secrets.token_bytes(COOKIE_BYTES)
            reply = self.build_handshake_packet(state.challenge_timestamp, state.challenge_cookie)
            mode = "challenge-from-normal"

        if reply:
            if mode.startswith("challenge") or mode == "ack":
                inner = reply
                reply = self.build_ares_envelope(inner)
                mode = f"ares-envelope-{mode}"
            sock.sendto(reply, addr)
            state.packets_out += 1
            self.log_event(
                "send",
                addr=f"{addr[0]}:{addr[1]}",
                mode=mode,
                length=len(reply),
                hex=reply.hex(),
            )

    def _json_safe_parsed(self, parsed: dict[str, object] | None) -> dict[str, object] | None:
        if parsed is None:
            return None
        out: dict[str, object] = {}
        for key, value in parsed.items():
            if isinstance(value, bytes):
                out[key] = value.hex()
            else:
                out[key] = value
        return out

    def run(self) -> None:
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_path.open("a", encoding="utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        self.log_event("listening", host=self.host, port=self.port, pid=os.getpid())

        try:
            while True:
                payload, addr = sock.recvfrom(65535)
                self.handle_packet(sock, payload, addr)
        finally:
            sock.close()
            if self.log_file:
                self.log_file.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal UE4/Ares UDP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument(
        "--log",
        default=r"C:\Users\Home\Desktop\project A\reverse-logs\ares_udp_server.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = AresUdpServer(args.host, args.port, Path(args.log) if args.log else None)
    server.run()


if __name__ == "__main__":
    main()
