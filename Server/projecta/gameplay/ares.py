"""Ares packet framing and stateless handshake helpers."""

from __future__ import annotations

import hashlib
import time
import zlib
from typing import Any


DDOS_RESERVED_PREFIX = b"\x00" * 8


def ares_crc32(data: bytes, seed: int = 0) -> int:
    return zlib.crc32(data, seed) & 0xFFFFFFFF


def prepend_ddos_reserved(packet: bytes) -> bytes:
    return DDOS_RESERVED_PREFIX + packet


def make_ares_frame(payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError("Ares frame payload is too large for uint16 length")
    checksum = ares_crc32(payload)
    return checksum.to_bytes(4, "little") + len(payload).to_bytes(2, "little") + payload


def append_packet_handler_marker(packet: bytes) -> bytes:
    """Append UE PacketHandler's byte-aligned bit-count marker."""
    return packet + b"\x01"


def append_packet_handler_marker_at_bit(packet: bytes, bit_count: int) -> bytes:
    """Append UE PacketHandler's bit-count marker at an exact bit offset."""
    if bit_count < 0 or bit_count > len(packet) * 8:
        raise ValueError("bit_count is outside the packet buffer")
    output = bytearray(packet[: (bit_count + 7) // 8])
    marker_byte_index = bit_count >> 3
    marker_bit_index = bit_count & 7
    if marker_byte_index == len(output):
        output.append(0)
    output[marker_byte_index] &= (1 << marker_bit_index) - 1
    output[marker_byte_index] |= 1 << marker_bit_index
    return bytes(output)


class BitWriter:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._bit_count = 0

    def write_bit(self, value: bool) -> None:
        byte_index = self._bit_count >> 3
        bit_index = self._bit_count & 7
        if byte_index == len(self._buffer):
            self._buffer.append(0)
        if value:
            self._buffer[byte_index] |= 1 << bit_index
        self._bit_count += 1

    def write_bytes(self, data: bytes) -> None:
        for byte in data:
            for bit_index in range(8):
                self.write_bit(bool(byte & (1 << bit_index)))

    def finish(self) -> bytes:
        return bytes(self._buffer)

    @property
    def bit_count(self) -> int:
        return self._bit_count


def make_stateless_component_payload(
    flag0: bool,
    flag1: bool,
    field_u32: int,
    cookie: bytes,
    extra_cookie: bytes | None = None,
) -> bytes:
    writer = BitWriter()
    writer.write_bit(flag0)
    writer.write_bit(flag1)
    writer.write_bytes((field_u32 & 0xFFFFFFFF).to_bytes(4, "little"))
    writer.write_bytes(cookie[:20].ljust(20, b"\x00"))
    if extra_cookie is not None:
        writer.write_bytes(extra_cookie[:20].ljust(20, b"\x00"))
    return writer.finish()


def stateless_component_bit_count(extra_cookie: bytes | None = None) -> int:
    bit_count = 2 + 32 + 160
    if extra_cookie is not None:
        bit_count += 160
    return bit_count


def make_stateless_component_payload_byte_aligned(
    flag0: bool,
    flag1: bool,
    field_u32: int,
    cookie: bytes,
    extra_cookie: bytes | None = None,
) -> bytes:
    first = (1 if flag0 else 0) | (2 if flag1 else 0)
    payload = bytes([first]) + (field_u32 & 0xFFFFFFFF).to_bytes(4, "little") + cookie[:20].ljust(20, b"\x00")
    if extra_cookie is not None:
        payload += extra_cookie[:20].ljust(20, b"\x00")
    return payload


def make_ares_frame_packet(payload: bytes, payload_bit_count: int | None = None, crc_includes_marker: bool = False) -> bytes:
    if payload_bit_count is None:
        return append_packet_handler_marker(make_ares_frame(payload))
    if payload_bit_count < 0 or payload_bit_count > len(payload) * 8:
        raise ValueError("payload_bit_count is outside the payload buffer")
    payload_length = (payload_bit_count + 7) // 8
    payload_bytes = payload[:payload_length]
    header = b"\x00" * 4 + payload_length.to_bytes(2, "little")
    bit_count = 48 + payload_bit_count
    packet_with_marker = append_packet_handler_marker_at_bit(header + payload_bytes, bit_count)
    checksum_payload = packet_with_marker[6 : 6 + payload_length] if crc_includes_marker else payload_bytes
    checksum = ares_crc32(checksum_payload)
    return checksum.to_bytes(4, "little") + packet_with_marker[4:]


def stateless_candidate_ares_packets(client_packet: bytes) -> list[dict[str, Any]]:
    token = client_packet[36:68] if len(client_packet) >= 68 else client_packet
    cookie_a = hashlib.sha1(b"project-a-local-stateless-cookie-a" + token).digest()
    cookie_b = hashlib.sha1(b"project-a-local-stateless-cookie-b" + token).digest()
    now = int(time.time()) & 0xFFFFFFFF
    payloads: list[tuple[str, bytes, int | None]] = [
        ("ares-empty", b"", None),
        ("stateless-bit-f10-u0-c20", make_stateless_component_payload(True, False, 0, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f01-u0-c20", make_stateless_component_payload(False, True, 0, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f11-u0-c20", make_stateless_component_payload(True, True, 0, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f10-u1-c20", make_stateless_component_payload(True, False, 1, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f10-time-c20", make_stateless_component_payload(True, False, now, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f10-u354-c40", make_stateless_component_payload(True, False, 354, cookie_a, cookie_b), stateless_component_bit_count(cookie_b)),
        ("stateless-aligned-f10-u0-c20", make_stateless_component_payload_byte_aligned(True, False, 0, cookie_a), None),
        ("stateless-aligned-f10-u354-c40", make_stateless_component_payload_byte_aligned(True, False, 354, cookie_a, cookie_b), None),
    ]
    candidates = []
    for name, payload, bit_count in payloads:
        wire = append_packet_handler_marker(make_ares_frame(payload))
        wire_exact_clean_crc = make_ares_frame_packet(payload, bit_count, crc_includes_marker=False) if bit_count is not None else wire
        wire_exact_marker_crc = make_ares_frame_packet(payload, bit_count, crc_includes_marker=True) if bit_count is not None else wire
        candidates.append({
            "candidate": name,
            "payload_hex": payload.hex(),
            "payload_bit_count": bit_count,
            "wire": wire,
            "wire_exact_clean_crc": wire_exact_clean_crc,
            "wire_exact_marker_crc": wire_exact_marker_crc,
            "wire_ddos": prepend_ddos_reserved(wire),
            "wire_ddos_exact_clean_crc": prepend_ddos_reserved(wire_exact_clean_crc),
            "wire_ddos_exact_marker_crc": prepend_ddos_reserved(wire_exact_marker_crc),
        })
    return candidates


def analyze_ares_frame(data: bytes) -> dict[str, Any] | None:
    if len(data) < 6:
        return None
    received = int.from_bytes(data[:4], "little")
    declared_length = int.from_bytes(data[4:6], "little")
    available = max(0, len(data) - 6)
    payload = data[6 : 6 + min(declared_length, available)]
    calculated = ares_crc32(payload)
    return {
        "received_checksum": received,
        "received_checksum_hex": f"{received:08x}",
        "declared_length": declared_length,
        "available_payload_length": available,
        "calculated_checksum": calculated,
        "calculated_checksum_hex": f"{calculated:08x}",
        "length_ok": declared_length == available,
        "checksum_ok": declared_length <= available and calculated == received,
    }


def make_handshake_ack_74(client_token: bytes, cookie_a: bytes) -> bytes:
    _ = client_token
    ack = bytearray(74)
    ack[8] = 0x02
    ack[32:36] = (303).to_bytes(4, "little")
    writer = BitWriter()
    writer.write_bit(True)
    writer.write_bit(False)
    writer.write_bytes((0).to_bytes(4, "little"))
    writer.write_bytes(cookie_a[:20].ljust(20, b"\x00"))
    payload = writer.finish()
    ack[36:36 + len(payload)] = payload
    return bytes(ack)


def make_raw_handshake_packet_74(u32_at_8: int, bit_count_at_32: int, payload: bytes) -> bytes:
    packet = bytearray(74)
    packet[8:12] = (u32_at_8 & 0xFFFFFFFF).to_bytes(4, "little")
    packet[32:36] = (bit_count_at_32 & 0xFFFFFFFF).to_bytes(4, "little")
    packet[36:36 + min(len(payload), 38)] = payload[:38]
    return bytes(packet)


def make_raw_stateless_packet_74(selector: int, cookie: bytes, tail: bytes, bit_count_at_32: int = 301) -> bytes:
    packet = bytearray(74)
    packet[8:12] = (((selector & 0xFFFF) << 16) | 0x19).to_bytes(4, "little")
    packet[12:32] = cookie[:20].ljust(20, b"\x00")
    packet[32:36] = (bit_count_at_32 & 0xFFFFFFFF).to_bytes(4, "little")
    packet[36:74] = tail[:38].ljust(38, b"\x00")
    return bytes(packet)


def stateless_final_ack_candidates(
    client_token: bytes,
    challenge_response_packet: bytes,
    cookie_a: bytes | None = None,
) -> list[dict[str, Any]]:
    """Generate deterministic final ACK candidates after the client response.

    These are protocol-lab candidates, not known-good gameplay packets. They let
    the observer test one variable at a time during live captures.
    """
    token = client_token[:32].ljust(32, b"\x00")
    cookie_a = cookie_a or hashlib.sha1(b"project-a-local-stateless-cookie-a" + token).digest()
    cookie_b = hashlib.sha1(b"project-a-local-stateless-cookie-b" + token).digest()
    response_cookie = challenge_response_packet[12:32] if len(challenge_response_packet) >= 32 else b""
    if len(response_cookie) < 20:
        response_cookie = cookie_a
    response_payload_len = challenge_response_packet[8] if len(challenge_response_packet) > 8 else 0
    response_payload = challenge_response_packet[36:36 + response_payload_len]
    response_tail = challenge_response_packet[36:74] if len(challenge_response_packet) >= 74 else token + b"\x00" * 6
    response_digest = hashlib.sha1(b"project-a-local-final-ack" + token + response_payload).digest()

    payloads: list[tuple[str, bytes, int | None]] = [
        ("final-bit-f10-u1-cookie-a", make_stateless_component_payload(True, False, 1, cookie_a), stateless_component_bit_count()),
        ("final-bit-f10-u2-cookie-a", make_stateless_component_payload(True, False, 2, cookie_a), stateless_component_bit_count()),
        ("final-bit-f10-u3-cookie-a", make_stateless_component_payload(True, False, 3, cookie_a), stateless_component_bit_count()),
        ("final-bit-f01-u1-cookie-a", make_stateless_component_payload(False, True, 1, cookie_a), stateless_component_bit_count()),
        ("final-bit-f11-u1-cookie-a", make_stateless_component_payload(True, True, 1, cookie_a), stateless_component_bit_count()),
        ("final-bit-f10-u1-response-cookie", make_stateless_component_payload(True, False, 1, response_cookie), stateless_component_bit_count()),
        ("final-bit-f10-u1-response-digest", make_stateless_component_payload(True, False, 1, response_digest), stateless_component_bit_count()),
        ("final-bit-f10-u354-cookie-pair", make_stateless_component_payload(True, False, 354, cookie_a, cookie_b), stateless_component_bit_count(cookie_b)),
        ("final-aligned-f10-u1-cookie-a", make_stateless_component_payload_byte_aligned(True, False, 1, cookie_a), None),
        ("final-aligned-f10-u2-cookie-a", make_stateless_component_payload_byte_aligned(True, False, 2, cookie_a), None),
        ("final-bit-f00-u0-cookie-a", make_stateless_component_payload(False, False, 0, cookie_a), stateless_component_bit_count()),
        ("final-bit-f10-u0-cookie-a", make_stateless_component_payload(True, False, 0, cookie_a), stateless_component_bit_count()),
        ("final-bit-f01-u0-cookie-a", make_stateless_component_payload(False, True, 0, cookie_a), stateless_component_bit_count()),
        ("final-bit-f11-u0-cookie-a", make_stateless_component_payload(True, True, 0, cookie_a), stateless_component_bit_count()),
        ("final-bit-f00-u1-cookie-a", make_stateless_component_payload(False, False, 1, cookie_a), stateless_component_bit_count()),
    ]

    candidates: list[dict[str, Any]] = []
    for name, payload, bit_count in payloads:
        candidates.append(
            {
                "candidate": f"raw74-{name}-u2-b303",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": make_raw_handshake_packet_74(2, 303, payload),
                "wire_key": "raw74",
            }
        )
        candidates.append(
            {
                "candidate": f"raw74-{name}-u3-b303",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": make_raw_handshake_packet_74(3, 303, payload),
                "wire_key": "raw74",
            }
        )
        if bit_count is not None:
            clean_wire = make_ares_frame_packet(payload, bit_count, crc_includes_marker=False)
            candidates.append(
                {
                    "candidate": f"ares-clean-{name}",
                    "payload_hex": payload.hex(),
                    "payload_bit_count": bit_count,
                    "wire": clean_wire,
                    "wire_key": "wire_exact_clean_crc",
                    "wire_ddos": prepend_ddos_reserved(clean_wire),
                    "wire_ddos_key": "wire_ddos_exact_clean_crc",
                }
            )
            marker_wire = make_ares_frame_packet(payload, bit_count, crc_includes_marker=True)
            candidates.append(
                {
                    "candidate": f"ares-marker-{name}",
                    "payload_hex": payload.hex(),
                    "payload_bit_count": bit_count,
                    "wire": marker_wire,
                    "wire_key": "wire_exact_marker_crc",
                    "wire_ddos": prepend_ddos_reserved(marker_wire),
                    "wire_ddos_key": "wire_ddos_exact_marker_crc",
                }
            )
        else:
            wire = append_packet_handler_marker(make_ares_frame(payload))
            candidates.append(
                {
                    "candidate": f"ares-byte-{name}",
                    "payload_hex": payload.hex(),
                    "payload_bit_count": bit_count,
                    "wire": wire,
                    "wire_key": "wire",
                    "wire_ddos": prepend_ddos_reserved(wire),
                    "wire_ddos_key": "wire_ddos",
                }
            )
    for selector in (3, 5, 7, 9, 13):
        for name, cookie in (("response-cookie", response_cookie), ("cookie-a", cookie_a)):
            candidates.append(
                {
                    "candidate": f"raw74-stateless-selector-{selector:02x}-{name}-b301-tail",
                    "payload_hex": response_tail.hex(),
                    "payload_bit_count": 301,
                    "wire": make_raw_stateless_packet_74(selector, cookie, response_tail, 301),
                    "wire_key": "raw74_stateless",
                }
            )
    return candidates
