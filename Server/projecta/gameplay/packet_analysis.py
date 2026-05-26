"""UDP packet analyzers used by the game-port observer."""

from __future__ import annotations

from typing import Any


def _looks_like_protected_game_packet(data: bytes) -> bool:
    return (
        len(data) >= 28
        and len(data) <= 512
        and len(data) != 74
        and data[:8] == b"\x00" * 8
        and len(data) >= 12
    )


def analyze_udp_packet(data: bytes) -> dict[str, Any]:
    nonzero_offsets = [idx for idx, value in enumerate(data) if value]
    u32le_offsets = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]
    u16le_offsets = [0, 2, 4, 6, 8, 32, 34, 36]
    u32le = {
        str(offset): int.from_bytes(data[offset : offset + 4], "little")
        for offset in u32le_offsets
        if len(data) >= offset + 4
    }
    u16le = {
        str(offset): int.from_bytes(data[offset : offset + 2], "little")
        for offset in u16le_offsets
        if len(data) >= offset + 2
    }
    tail = data[36:] if len(data) > 36 else b""
    return {
        "length": len(data),
        "first_nonzero_offset": nonzero_offsets[0] if nonzero_offsets else None,
        "nonzero_offset_count": len(nonzero_offsets),
        "nonzero_offsets_first32": nonzero_offsets[:32],
        "u16le": u16le,
        "u32le": u32le,
        "first8_zero": len(data) >= 8 and data[:8] == b"\x00" * 8,
        "byte8": data[8] if len(data) > 8 else None,
        "u32le_at_32": u32le.get("32"),
        "tail_offset36_length": len(tail),
        "tail_offset36_unique_bytes": sorted(set(tail)),
        "project_a_74_byte_probe_candidate": (
            len(data) == 74
            and data[:8] == b"\x00" * 8
            and len(data) > 8
            and data[8] == 1
            and u32le.get("32") == 296
        ),
        "project_a_stateless_response_74_candidate": (
            len(data) == 74
            and data[:8] == b"\x00" * 8
            and len(data) > 8
            and data[8] in {0x19, 0x2D}
            and u32le.get("32") == 303
        ),
        "project_a_protected_game_packet_candidate": (
            _looks_like_protected_game_packet(data)
        ),
        "protected_counter_u32_at_8": int.from_bytes(data[8:12], "little") if len(data) >= 12 and data[:8] == b"\x00" * 8 else None,
    }


def analyze_protected_game_packet(data: bytes, previous_counter: int | None = None) -> dict[str, Any] | None:
    if not _looks_like_protected_game_packet(data):
        return None
    counter = int.from_bytes(data[8:12], "little")
    payload = data[12:]
    delta = None if previous_counter is None else (counter - previous_counter) & 0xFFFFFFFF
    return {
        "kind": "project_a_protected_game_packet",
        "ddos_reserved_bits": 64,
        "ddos_reserved_hex": data[:8].hex(),
        "ares_counter_u32": counter,
        "ares_counter_hex": f"{counter:08x}",
        "ares_counter_delta": delta,
        "protected_payload_offset": 12,
        "protected_payload_length": len(payload),
        "protected_payload_hex": payload.hex(),
        "protected_payload_first16_hex": payload[:16].hex(),
        "protected_payload_unique_bytes": sorted(set(payload)),
    }


def analyze_client_initial_probe_74(data: bytes) -> dict[str, Any] | None:
    if not (
        len(data) == 74
        and data[:8] == b"\x00" * 8
        and data[8:12] == b"\x01\x00\x00\x00"
        and int.from_bytes(data[32:36], "little") == 296
    ):
        return None
    token = data[36:68]
    return {
        "kind": "project_a_client_initial_probe_74",
        "unknown_u32_at_8": int.from_bytes(data[8:12], "little"),
        "zero_padding_12_32": data[12:32] == b"\x00" * 20,
        "payload_bit_count_at_32": int.from_bytes(data[32:36], "little"),
        "client_token_offset": 36,
        "client_token_length": len(token),
        "client_token_hex": token.hex(),
        "trailer_hex": data[68:74].hex(),
    }


def analyze_client_challenge_response_74(data: bytes) -> dict[str, Any] | None:
    if not (
        len(data) == 74
        and data[:8] == b"\x00" * 8
        and len(data) > 8
        and data[8] in {0x19, 0x2D}
    ):
        return None
    payload_byte_len = data[8]
    bit_count_at_32 = int.from_bytes(data[32:36], "little") if len(data) >= 36 else 0
    payload = data[36:36 + payload_byte_len] if len(data) >= 36 + payload_byte_len else data[36:]
    return {
        "kind": "project_a_client_challenge_response_74",
        "payload_byte_length": payload_byte_len,
        "u32_at_8": int.from_bytes(data[8:12], "little"),
        "selector_at_10": int.from_bytes(data[10:12], "little"),
        "component_payload_12_32_hex": data[12:32].hex(),
        "bit_count_at_32": bit_count_at_32,
        "payload_offset": 36,
        "payload_hex": payload.hex(),
        "trailer_hex": data[36 + payload_byte_len:].hex() if len(data) > 36 + payload_byte_len else "",
    }
