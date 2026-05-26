"""Ares packet framing and stateless handshake helpers."""

from __future__ import annotations

import hashlib
import struct
import time
import zlib
from typing import Any


DDOS_RESERVED_PREFIX = b"\x00" * 8


def ares_crc32(data: bytes, seed: int = 0) -> int:
    return zlib.crc32(data, seed) & 0xFFFFFFFF


ARES_TRANSFORM_TABLE = bytes.fromhex(
    "d6f0de79a73956bf07df008caa3e109a891e4625a84595c0234136815db07b49"
    "dacc2a1ce7a466967348cfb86f1fca8f3cf8aba322e61bb4ea0a43f5c1b178"
    "8db3acd74d98a1804476bc55fe125131ffa5db4e4ab9900fc3e92706b219d5"
    "ad9175c687f3142d24d164027d5f018b1126c9746d9f29ef86345aae5efdd4"
    "d0676e9c6016099913831a18a088c49d7ef67a3dbd94cd323003cee8151d"
    "3f82bb358e0bfa3a59afd82c5bed47ebd24b0d4f4c33f9ee0885d3fb9e20"
    "ec69e468e35352f2b5e09221a993f73b4204f16bc5c8b658e1409717575c"
    "2f61d9c2a205dd62f4289b2e546c63fc386ae5a6ba72dc3777717c7fbe0e"
    "50c784e20c2b65708ab7cb"
)


MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF


def _u32(value: int) -> int:
    return value & MASK32


def _u64(value: int) -> int:
    return value & MASK64


def _rol32(value: int, count: int) -> int:
    value &= MASK32
    count &= 31
    return ((value << count) | (value >> (32 - count))) & MASK32 if count else value


def _ror32(value: int, count: int) -> int:
    value &= MASK32
    count &= 31
    return ((value >> count) | (value << (32 - count))) & MASK32 if count else value


def _rol64(value: int, count: int) -> int:
    value &= MASK64
    count &= 63
    return ((value << count) | (value >> (64 - count))) & MASK64 if count else value


def _ror64(value: int, count: int) -> int:
    value &= MASK64
    count &= 63
    return ((value >> count) | (value << (64 - count))) & MASK64 if count else value


def _ror8(value: int, count: int) -> int:
    value &= 0xFF
    count &= 7
    return ((value >> count) | (value << (8 - count))) & 0xFF if count else value


def _rol8(value: int, count: int) -> int:
    value &= 0xFF
    count &= 7
    return ((value << count) | (value >> (8 - count))) & 0xFF if count else value


def _seed_mix(seed: int, additive: int = 0) -> int:
    """Port of the 64-bit state setup in Ares transform `0x2766410`."""
    x = _u32(seed + additive)
    folded = ((x >> 15) ^ x) >> 12
    shifted = _u32((seed + additive - 6) << 25)
    return _u64((folded ^ shifted ^ x) * 0x2545F4914F6CDD1D)


def _mod_plus_one(value: int, modulus: int) -> int:
    return int(value % modulus) + 1


def _swap_bits32(value: int) -> int:
    value &= MASK32
    x = (((value >> 1) ^ (value << 1)) & 0x55555555) ^ _u32(value << 1)
    y = (((x >> 2) ^ (x << 2)) & 0x33333333) ^ _u32(x << 2)
    z = (((y >> 4) ^ (y << 4)) & 0x0F0F0F0F) ^ _u32(y << 4)
    return z & MASK32


def _swap_bits64(value: int, mask1: int) -> int:
    value &= MASK64
    x = (((value >> 1) ^ (value << 1)) & mask1) ^ _u64(value << 1)
    y = (((x >> 2) ^ (x << 2)) & 0x3333333333333333) ^ _u64(x << 2)
    z = (((y >> 4) ^ (y << 4)) & 0x0F0F0F0F0F0F0F0F) ^ _u64(y << 4)
    return z & MASK64


def _swap_byte_twice(value: int) -> int:
    value &= 0xFF
    x = ((((value >> 1) ^ ((value << 1) & 0xFF)) & 0x55) ^ ((value << 1) & 0xFF)) & 0xFF
    y = ((((x >> 1) ^ ((x << 1) & 0xFF)) & 0x55) ^ ((x << 1) & 0xFF)) & 0xFF
    return y


def _byte_table_transform(value: int) -> int:
    table_value = ARES_TRANSFORM_TABLE[value & 0xFF]
    mixed = ((table_value * 0x8020) & 0x88440) | ((table_value * 0x802) & 0x22110)
    return (~((mixed * 0x10101) >> 16)) & 0xFF


ARES_INVERSE_BYTE_TABLE = bytes(
    sorted(range(256), key=lambda value: _byte_table_transform(value))
)


def _swap_word_bytes32(value: int) -> int:
    value &= MASK32
    return ((((value >> 8) ^ (value << 8)) & 0x00FF00FF) ^ _u32(value << 8)) & MASK32


def _swap_word_bytes64(value: int) -> int:
    value &= MASK64
    return ((((value >> 8) ^ (value << 8)) & 0x00FF00FF00FF00FF) ^ _u64(value << 8)) & MASK64


def ares_transform_outgoing(packet: bytes, seed: int, bit_count: int | None = None) -> tuple[bytes, int]:
    """Apply Valorant/Ares outgoing PacketHandler transform from `0x2766410`.

    The transform mutates the Ares frame before the outer PacketHandler marker.
    Returns `(transformed_packet, next_seed_guess)`; the second value mirrors the
    rolling state high dword visible in the routine and is useful for experiments.
    """
    if bit_count is None:
        bit_count = len(packet) * 8
    if bit_count < 0 or bit_count > len(packet) * 8:
        raise ValueError("bit_count is outside packet buffer")

    data = bytearray(packet)
    seed = _u32(seed)
    state_a = _seed_mix(seed, 0x4ED47AFA)
    state_b = _seed_mix(seed, 0)
    rolling = seed
    remaining = bit_count
    offset = 0
    mask1_64 = 0x5555555555555555
    xor64 = 0xAAAAAAAAAAAAAAAA

    while remaining >= 64:
        rolling = _ror32(rolling, 2)
        rot_a = _ror32(rolling, 1)
        rot_b = _ror32(rot_a, 2)
        rot_c = _ror32(rot_b, 1)
        rot_d = _ror32(rot_c, 1)
        rot_e = _ror32(rot_d, 1)

        chunk = int.from_bytes(data[offset : offset + 8], "little")
        mixed = _swap_bits64(chunk, mask1_64)

        rot_c = _mod_plus_one(rot_c, 63)
        rot_a = _mod_plus_one(rot_a, 63)
        rolling = _mod_plus_one(rolling, 63)

        x = (((mixed >> 8) ^ (mixed << 8)) & 0x00FF00FF00FF00FF) ^ _u64(mixed << 8)
        x = _rol64(x, 32)
        x = _rol64(x, rolling)
        x = _rol64(x, rot_a)
        x = _u64(x + rot_e)
        x = _ror64(x, rot_c)
        x ^= xor64
        x = _u64(x - rot_e)
        data[offset : offset + 8] = x.to_bytes(8, "little")

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 8
        remaining -= 64

    while remaining >= 32:
        rolling = _rol32(rolling, 2)
        rot_a = _rol32(rolling, 1)
        rot_b = _rol32(rot_a, 2)
        rot_c = _rol32(rot_b, 1)
        rot_d = _rol32(rot_c, 1)
        rot_e = _rol32(rot_d, 1)

        chunk = int.from_bytes(data[offset : offset + 4], "little")
        mixed = _swap_bits32(chunk)

        rot_c = _mod_plus_one(rot_c, 31)
        rot_a = _mod_plus_one(rot_a, 31)
        rolling = _mod_plus_one(rolling, 31)

        x = (((mixed >> 8) ^ (mixed << 8)) & 0x00FF00FF) ^ _u32(mixed << 8)
        x = _rol32(x, 16)
        x = _rol32(x, rolling)
        x = _rol32(x, rot_a)
        x = _u32(x + rot_b)
        x = _ror32(x, rot_c)
        x ^= rot_d
        x = _u32(x - rot_e)
        data[offset : offset + 4] = x.to_bytes(4, "little")

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 4
        remaining -= 32

    while remaining >= 8:
        rot = _mod_plus_one(_u32(rolling * 11), 7)
        state_byte = _u32(_u32(rolling * 11) * 0x533) & 0xFF
        x = _ror8(data[offset], rot)
        x = _swap_byte_twice(x) ^ state_byte
        data[offset] = _byte_table_transform(x)

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 1
        remaining -= 8

    if remaining:
        # Tail bits are rare for current byte-aligned protected experiments.
        mask = (1 << remaining) - 1
        state_mask = (rolling ^ 0xFA) & mask
        data[offset] ^= state_mask
        state_sum = _u64(state_b + state_a)
        rolling = (state_sum >> 32) & MASK32

    return bytes(data), rolling


def ares_transform_incoming(packet: bytes, seed: int, bit_count: int | None = None) -> tuple[bytes, int]:
    """Reverse `ares_transform_outgoing` for byte-aligned protected packets."""
    if bit_count is None:
        bit_count = len(packet) * 8
    if bit_count < 0 or bit_count > len(packet) * 8:
        raise ValueError("bit_count is outside packet buffer")

    data = bytearray(packet)
    seed = _u32(seed)
    state_a = _seed_mix(seed, 0x4ED47AFA)
    state_b = _seed_mix(seed, 0)
    rolling = seed
    remaining = bit_count
    offset = 0
    mask1_64 = 0x5555555555555555
    xor64 = 0xAAAAAAAAAAAAAAAA

    while remaining >= 64:
        rolling = _ror32(rolling, 2)
        rot_a = _ror32(rolling, 1)
        rot_b = _ror32(rot_a, 2)
        rot_c = _ror32(rot_b, 1)
        rot_d = _ror32(rot_c, 1)
        rot_e = _ror32(rot_d, 1)

        rot_c = _mod_plus_one(rot_c, 63)
        rot_a = _mod_plus_one(rot_a, 63)
        rolling = _mod_plus_one(rolling, 63)

        x = int.from_bytes(data[offset : offset + 8], "little")
        x = _u64(x + rot_e)
        x ^= xor64
        x = _rol64(x, rot_c)
        x = _u64(x - rot_e)
        x = _ror64(x, rot_a)
        x = _ror64(x, rolling)
        x = _ror64(x, 32)
        x = _swap_word_bytes64(x)
        x = _swap_bits64(x, mask1_64)
        data[offset : offset + 8] = x.to_bytes(8, "little")

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 8
        remaining -= 64

    while remaining >= 32:
        rolling = _rol32(rolling, 2)
        rot_a = _rol32(rolling, 1)
        rot_b = _rol32(rot_a, 2)
        rot_c = _rol32(rot_b, 1)
        rot_d = _rol32(rot_c, 1)
        rot_e = _rol32(rot_d, 1)

        rot_c = _mod_plus_one(rot_c, 31)
        rot_a = _mod_plus_one(rot_a, 31)
        rolling = _mod_plus_one(rolling, 31)

        x = int.from_bytes(data[offset : offset + 4], "little")
        x = _u32(x + rot_e)
        x ^= rot_d
        x = _rol32(x, rot_c)
        x = _u32(x - rot_b)
        x = _ror32(x, rot_a)
        x = _ror32(x, rolling)
        x = _ror32(x, 16)
        x = _swap_word_bytes32(x)
        x = _swap_bits32(x)
        data[offset : offset + 4] = x.to_bytes(4, "little")

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 4
        remaining -= 32

    while remaining >= 8:
        rot = _mod_plus_one(_u32(rolling * 11), 7)
        state_byte = _u32(_u32(rolling * 11) * 0x533) & 0xFF
        x = ARES_INVERSE_BYTE_TABLE[data[offset]]
        x ^= state_byte
        x = _swap_byte_twice(x)
        data[offset] = _rol8(x, rot)

        state_sum = _u64(state_b + state_a)
        state_b ^= state_a
        state_a = _ror64(state_a, 9) ^ _u64(state_b << 14) ^ state_b
        state_b = _ror64(state_b, 28)
        rolling = (state_sum >> 32) & MASK32
        offset += 1
        remaining -= 8

    if remaining:
        mask = (1 << remaining) - 1
        state_mask = (rolling ^ 0xFA) & mask
        data[offset] ^= state_mask
        state_sum = _u64(state_b + state_a)
        rolling = (state_sum >> 32) & MASK32

    return bytes(data), rolling


def unwrap_ares_protected_payload(payload: bytes, seeds: list[int]) -> dict[str, Any] | None:
    """Try protected-payload seeds and return first CRC-valid Ares frame."""
    candidates: list[bytes] = [payload]
    if payload:
        candidates.append(payload[:-1])
    seen: set[tuple[int, int]] = set()
    for seed in seeds:
        for candidate in candidates:
            key = (seed, len(candidate))
            if key in seen or len(candidate) < 6:
                continue
            seen.add(key)
            unwrapped, next_seed = ares_transform_incoming(candidate, seed)
            frame = analyze_ares_frame(unwrapped)
            if frame and frame.get("checksum_ok"):
                return {
                    "seed": seed,
                    "next_seed": next_seed,
                    "frame": unwrapped,
                    "frame_length": len(unwrapped),
                    "dropped_marker": len(candidate) != len(payload),
                    "declared_length": frame.get("declared_length"),
                    "payload_hex": unwrapped[6:6 + frame["declared_length"]].hex(),
                }
    return None


def make_ares_protected_frame_packet(payload: bytes, seed: int) -> bytes:
    transformed, _ = ares_transform_outgoing(make_ares_frame(payload), seed)
    return append_packet_handler_marker(transformed)


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


def make_ue_stateless_component_payload(
    *,
    handshake_packet: bool = True,
    restart_handshake: bool = False,
    secret_id: bool = False,
    timestamp: float = 0.0,
    cookie: bytes,
    extra_cookie: bytes | None = None,
) -> bytes:
    """UE4 StatelessConnectHandlerComponent bit layout from 4.22 source."""
    writer = BitWriter()
    writer.write_bit(handshake_packet)
    writer.write_bit(restart_handshake)
    writer.write_bit(secret_id)
    writer.write_bytes(struct.pack("<f", timestamp))
    writer.write_bytes(cookie[:20].ljust(20, b"\x00"))
    if extra_cookie is not None:
        writer.write_bytes(extra_cookie[:20].ljust(20, b"\x00"))
    return writer.finish()


def stateless_component_bit_count(extra_cookie: bytes | None = None) -> int:
    bit_count = 2 + 32 + 160
    if extra_cookie is not None:
        bit_count += 160
    return bit_count


def ue_stateless_component_bit_count(extra_cookie: bytes | None = None) -> int:
    bit_count = 3 + 32 + 160
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
    now_float = float(now & 0x00FFFFFF)
    payloads: list[tuple[str, bytes, int | None]] = [
        ("ares-empty", b"", None),
        ("stateless-bit-f10-u0-c20", make_stateless_component_payload(True, False, 0, cookie_a), stateless_component_bit_count()),
        ("ue-stateless-challenge-secret0-time-cookie-a", make_ue_stateless_component_payload(secret_id=False, timestamp=now_float, cookie=cookie_a), ue_stateless_component_bit_count()),
        ("ue-stateless-challenge-secret1-time-cookie-a", make_ue_stateless_component_payload(secret_id=True, timestamp=now_float, cookie=cookie_a), ue_stateless_component_bit_count()),
        ("stateless-bit-f10-u1-c20", make_stateless_component_payload(True, False, 1, cookie_a), stateless_component_bit_count()),
        ("stateless-bit-f10-time-c20", make_stateless_component_payload(True, False, now, cookie_a), stateless_component_bit_count()),
        ("ue-stateless-restart-response-cookie-pair", make_ue_stateless_component_payload(secret_id=False, timestamp=now_float, cookie=cookie_a, extra_cookie=cookie_b), ue_stateless_component_bit_count(cookie_b)),
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


def make_ue_stateless_challenge_ack(cookie: bytes) -> bytes:
    payload = make_ue_stateless_component_payload(
        handshake_packet=True,
        restart_handshake=False,
        secret_id=True,
        timestamp=-1.0,
        cookie=cookie,
    )
    return make_ares_frame_packet(payload, ue_stateless_component_bit_count(), crc_includes_marker=False)


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


def make_raw_stateless_packet_74_from_payload(selector: int, payload: bytes, tail: bytes, bit_count_at_32: int = 301) -> bytes:
    packet = bytearray(74)
    packet[8:12] = (((selector & 0xFFFF) << 16) | 0x19).to_bytes(4, "little")
    packet[12:32] = payload[:20].ljust(20, b"\x00")
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
    source_check_payloads = [
        ("ue-final-ack-neg1-cookie-a", make_ue_stateless_component_payload(secret_id=True, timestamp=-1.0, cookie=cookie_a), ue_stateless_component_bit_count()),
        ("ue-final-ack-neg1-response-cookie", make_ue_stateless_component_payload(secret_id=True, timestamp=-1.0, cookie=response_cookie), ue_stateless_component_bit_count()),
        ("ue-final-ack-neg1-secret0-cookie-a", make_ue_stateless_component_payload(secret_id=False, timestamp=-1.0, cookie=cookie_a), ue_stateless_component_bit_count()),
    ]
    for name, payload, bit_count in source_check_payloads:
        clean_wire = make_ares_frame_packet(payload, bit_count, crc_includes_marker=False)
        candidates.append(
            {
                "candidate": f"source-check-ares-clean-{name}",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": clean_wire,
                "wire_key": "wire_exact_clean_crc",
                "wire_ddos": prepend_ddos_reserved(clean_wire),
                "wire_ddos_key": "wire_ddos_exact_clean_crc",
            }
        )
        candidates.append(
            {
                "candidate": f"source-check-ddos-ares-clean-{name}",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": prepend_ddos_reserved(clean_wire),
                "wire_key": "wire_ddos_exact_clean_crc",
            }
        )
        marker_wire = make_ares_frame_packet(payload, bit_count, crc_includes_marker=True)
        candidates.append(
            {
                "candidate": f"source-check-ares-marker-{name}",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": marker_wire,
                "wire_key": "wire_exact_marker_crc",
                "wire_ddos": prepend_ddos_reserved(marker_wire),
                "wire_ddos_key": "wire_ddos_exact_marker_crc",
            }
        )
        candidates.append(
            {
                "candidate": f"source-check-ddos-ares-marker-{name}",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": prepend_ddos_reserved(marker_wire),
                "wire_key": "wire_ddos_exact_marker_crc",
            }
        )
    for name, cookie in (("response-cookie", response_cookie), ("cookie-a", cookie_a)):
        candidates.append(
            {
                "candidate": f"observed-raw74-stateless-selector-05-{name}-b299-tail",
                "payload_hex": response_tail.hex(),
                "payload_bit_count": 299,
                "wire": make_raw_stateless_packet_74(5, cookie, response_tail, 299),
                "wire_key": "raw74_stateless_observed",
            }
        )
    ack_payloads = [
        ("ack-payload-f10-u1-cookie-a", make_stateless_component_payload(True, False, 1, cookie_a), 303),
        ("ack-payload-f10-u0-cookie-a", make_stateless_component_payload(True, False, 0, cookie_a), 303),
        ("ack-payload-ue-neg1-cookie-a", make_ue_stateless_component_payload(secret_id=True, timestamp=-1.0, cookie=cookie_a), 303),
    ]
    for name, payload, bit_count in ack_payloads:
        candidates.append(
            {
                "candidate": f"observed-raw74-selector-03-{name}-tail",
                "payload_hex": payload.hex(),
                "payload_bit_count": bit_count,
                "wire": make_raw_stateless_packet_74_from_payload(3, payload, response_tail, bit_count),
                "wire_key": "raw74_payload_tail",
            }
        )
    ue_final_payload = make_ue_stateless_component_payload(secret_id=True, timestamp=-1.0, cookie=cookie_a)
    stripped_ue_final_payload = ue_final_payload[2:]
    for selector in (3, 5):
        candidates.append(
            {
                "candidate": f"observed-raw74-selector-{selector:02x}-ue-neg1-stripped-cookie-a-b299-tail",
                "payload_hex": stripped_ue_final_payload.hex(),
                "payload_bit_count": 299,
                "wire": make_raw_stateless_packet_74_from_payload(selector, stripped_ue_final_payload, response_tail, 299),
                "wire_key": "raw74_payload_tail_observed_stripped",
            }
        )
    return candidates
