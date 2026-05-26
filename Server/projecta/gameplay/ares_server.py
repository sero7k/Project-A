"""Standalone minimal Ares/UE4 UDP server for protocol logging.

Implements the UE4.22 stateless connect handshake (challenge → response → ack)
and logs every packet to JSONL. Use for traffic capture; not a full game server.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from .ares import (
    analyze_ares_frame,
    make_ares_frame_packet,
    make_ue_stateless_component_payload,
    ue_stateless_component_bit_count,
)


COOKIE_BYTES = 20
HANDSHAKE_PACKET_BITS = 195
RESTART_RESPONSE_BITS = 355


class _BitStream:
    """Incoming bit-stream reader for UE4 StatelessConnectHandlerComponent packets."""

    def __init__(self, data: bytes) -> None:
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


@dataclass
class _ClientState:
    challenge_cookie: bytes = field(default_factory=lambda: b"\x00" * COOKIE_BYTES)
    challenge_timestamp: float = 0.0
    connected: bool = False
    last_seen: float = 0.0
    packets_in: int = 0
    packets_out: int = 0


def _json_default(obj: object) -> object:
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"not serializable: {type(obj)}")


class AresUdpServer:
    """Minimal UE4/Ares UDP server implementing the stateless connect handshake.

    Handles the challenge→response→ack flow and logs every packet to JSONL.
    """

    def __init__(self, host: str, port: int, log_path: Path | None) -> None:
        self.host = host
        self.port = port
        self.log_path = log_path
        self.clients: dict[tuple[str, int], _ClientState] = {}
        self.started_at = time.monotonic()
        self._log_file = None

    def server_time(self) -> float:
        return float(time.monotonic() - self.started_at + 1.0)

    def log_event(self, event: str, **fields: object) -> None:
        record = {"ts": time.time(), "event": event, **fields}
        line = json.dumps(record, default=_json_default, separators=(",", ":"))
        print(line, flush=True)
        if self._log_file:
            self._log_file.write(line + "\n")
            self._log_file.flush()

    def _build_challenge(self, timestamp: float, cookie: bytes) -> bytes:
        payload = make_ue_stateless_component_payload(
            handshake_packet=True,
            restart_handshake=False,
            secret_id=False,
            timestamp=timestamp,
            cookie=cookie,
        )
        return make_ares_frame_packet(payload, ue_stateless_component_bit_count(), crc_includes_marker=False)

    def _build_ack(self, cookie: bytes) -> bytes:
        payload = make_ue_stateless_component_payload(
            handshake_packet=True,
            restart_handshake=False,
            secret_id=True,
            timestamp=-1.0,
            cookie=cookie,
        )
        return make_ares_frame_packet(payload, ue_stateless_component_bit_count(), crc_includes_marker=False)

    def _parse_stateless_handshake(self, payload: bytes) -> dict[str, object] | None:
        bits = _BitStream(payload)
        try:
            if bits.read_bit() != 1:
                return {"handshake": False}
            remaining = bits.bits_left()
            expected = HANDSHAKE_PACKET_BITS - 1
            restart_expected = RESTART_RESPONSE_BITS - 1
            rounded_expected = ((HANDSHAKE_PACKET_BITS + 7) // 8) * 8 - 1
            rounded_restart_expected = ((RESTART_RESPONSE_BITS + 7) // 8) * 8 - 1
            if remaining not in {expected, restart_expected, rounded_expected, rounded_restart_expected}:
                return {"handshake": True, "valid": False, "bits_left": remaining}
            restart = bool(bits.read_bit())
            secret_id = bits.read_bit()
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

    def handle_packet(self, sock: socket.socket, data: bytes, addr: tuple[str, int]) -> None:
        state = self.clients.setdefault(addr, _ClientState())
        state.last_seen = time.time()
        state.packets_in += 1

        ares_frame = analyze_ares_frame(data)
        inner = data[6 : 6 + ares_frame["declared_length"]] if (ares_frame and ares_frame.get("checksum_ok")) else data
        parsed = self._parse_stateless_handshake(inner)

        self.log_event(
            "recv",
            addr=f"{addr[0]}:{addr[1]}",
            length=len(data),
            hex=data.hex(),
            ares_ok=bool(ares_frame and ares_frame.get("checksum_ok")),
            parsed=parsed,
        )

        reply: bytes | None = None
        mode = "none"

        if parsed and parsed.get("handshake") is True and parsed.get("valid") is True:
            timestamp = float(parsed.get("timestamp") or 0.0)
            cookie = parsed.get("cookie")
            if not isinstance(cookie, bytes):
                cookie = b"\x00" * COOKIE_BYTES
            if timestamp == 0.0:
                state.challenge_timestamp = self.server_time()
                state.challenge_cookie = secrets.token_bytes(COOKIE_BYTES)
                reply = self._build_challenge(state.challenge_timestamp, state.challenge_cookie)
                mode = "challenge"
            else:
                state.connected = True
                state.challenge_cookie = cookie
                reply = self._build_ack(cookie)
                mode = "ack"
        elif parsed and parsed.get("handshake") is False:
            state.challenge_timestamp = self.server_time()
            state.challenge_cookie = secrets.token_bytes(COOKIE_BYTES)
            reply = self._build_challenge(state.challenge_timestamp, state.challenge_cookie)
            mode = "challenge-from-normal"

        if reply:
            sock.sendto(reply, addr)
            state.packets_out += 1
            self.log_event("send", addr=f"{addr[0]}:{addr[1]}", mode=mode, length=len(reply), hex=reply.hex())

    def run(self) -> None:
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = self.log_path.open("a", encoding="utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        self.log_event("listening", host=self.host, port=self.port, pid=os.getpid())

        try:
            while True:
                data, addr = sock.recvfrom(65535)
                self.handle_packet(sock, data, addr)
        finally:
            sock.close()
            if self._log_file:
                self._log_file.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal UE4/Ares UDP server for protocol logging")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--log", default="reverse-logs/ares_udp_server.jsonl")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    server = AresUdpServer(args.host, args.port, Path(args.log) if args.log else None)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
