"""Stateful Ares handshake handling for the UDP observer."""

from __future__ import annotations

import hashlib
import os
import socket
import threading
from pathlib import Path
from typing import Any

from .ares import (
    analyze_ares_frame,
    append_packet_handler_marker,
    make_ares_frame,
    make_ares_protected_frame_packet,
    make_ares_frame_packet,
    make_handshake_ack_74,
    make_stateless_component_payload,
    stateless_candidate_ares_packets,
    stateless_component_bit_count,
    stateless_final_ack_candidates,
    unwrap_ares_protected_payload,
)
from .event_log import append_event
from .ue_control_channel import UE4ControlChannelHandler, build_login_complete, build_welcome_response


HANDSHAKE_STATE_AWAITING_PROBE = "awaiting_probe"
HANDSHAKE_STATE_AWAITING_RESPONSE = "awaiting_response"
HANDSHAKE_STATE_CONNECTED = "connected"
_SELECTOR5_PROTECTED_SENT: set[tuple[str, int]] = set()


def _parse_seed_list(raw: str) -> list[int]:
    seeds: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        seeds.append(int(part, 0) & 0xFFFFFFFF)
    return seeds


def _ares_payload_from_packet(packet: bytes) -> bytes:
    if len(packet) < 6:
        return b""
    declared = int.from_bytes(packet[4:6], "little")
    return packet[6:6 + declared]


def _selector5_protected_seeds() -> list[int]:
    raw = os.environ.get("PROJECT_A_SELECTOR5_PROTECTED_SEEDS", "").strip()
    if not raw:
        return []
    return _parse_seed_list(raw)


def _protected_reply_seeds() -> list[int]:
    raw = os.environ.get("PROJECT_A_PROTECTED_REPLY_SEEDS", "").strip()
    if raw:
        return _parse_seed_list(raw)
    seeds = _selector5_protected_seeds()
    return seeds if seeds else [0]


def _protected_seed_candidates(protected_packet: dict[str, Any] | None) -> list[int]:
    seeds = list(_protected_reply_seeds())
    if protected_packet:
        counter = int(protected_packet.get("ares_counter_u32", 0)) & 0xFFFFFFFF
        seeds.extend([
            counter,
            (counter - 2) & 0xFFFFFFFF,
            (counter - 1) & 0xFFFFFFFF,
            (counter + 1) & 0xFFFFFFFF,
            (counter + 2) & 0xFFFFFFFF,
        ])
    deduped: list[int] = []
    seen: set[int] = set()
    for seed in seeds:
        seed &= 0xFFFFFFFF
        if seed not in seen:
            seen.add(seed)
            deduped.append(seed)
    return deduped


def _ue_game_mode_for_welcome(game_state: dict[str, Any] | None) -> str:
    return os.environ.get(
        "PROJECT_A_UE_GAME_MODE",
        "/Script/ShooterGame.ShooterGameMode",
    )


def _is_valid_unprotected_ares_frame(data: bytes) -> bool:
    frame = analyze_ares_frame(data)
    return bool(frame and frame.get("checksum_ok") and frame.get("length_ok"))


def _send_final_ack_candidates(
    *,
    sock: socket.socket,
    addr: tuple[str, int],
    endpoint: str,
    token: bytes,
    cookie_a: bytes,
    challenge_response_packet: bytes,
    handshake_final_sequence: list[int],
    log_path: Path,
    lock: threading.Lock,
    event_name: str,
) -> None:
    candidates = stateless_final_ack_candidates(token, challenge_response_packet, cookie_a)
    append_event(log_path, lock, {
        "event": f"{event_name}_ready",
        "endpoint": endpoint,
        "candidate_count": len(candidates),
        "sequence": handshake_final_sequence,
    })
    for sequence_index, candidate_index in enumerate(handshake_final_sequence):
        if candidate_index < 0 or candidate_index >= len(candidates):
            append_event(log_path, lock, {
                "event": f"{event_name}_error",
                "endpoint": endpoint,
                "candidate_index": candidate_index,
                "error": "candidate index out of range",
            })
            continue
        candidate = candidates[candidate_index]
        packet = candidate["wire"]
        try:
            sock.sendto(packet, addr)
            append_event(log_path, lock, {
                "event": f"{event_name}_sent",
                "endpoint": endpoint,
                "state": HANDSHAKE_STATE_CONNECTED,
                "sequence_index": sequence_index,
                "candidate_index": candidate_index,
                "candidate": candidate["candidate"],
                "wire_key": candidate.get("wire_key"),
                "payload_hex": candidate.get("payload_hex"),
                "payload_bit_count": candidate.get("payload_bit_count"),
                "hex": packet.hex(),
                "length": len(packet),
            })
        except OSError as exc:
            append_event(log_path, lock, {
                "event": f"{event_name}_error",
                "endpoint": endpoint,
                "candidate_index": candidate_index,
                "candidate": candidate["candidate"],
                "error": repr(exc),
            })


def handle_ares_handshake_packet(
    *,
    sock: socket.socket,
    addr: tuple[str, int],
    endpoint: str,
    data: bytes,
    initial_probe: dict[str, Any] | None,
    challenge_response: dict[str, Any] | None,
    protected_packet: dict[str, Any] | None,
    handshake_states: dict[str, str],
    handshake_tokens: dict[str, bytes],
    handshake_cookies: dict[str, bytes],
    handshake_final_sequence: list[int] | None,
    control_handlers: dict[str, UE4ControlChannelHandler] | None = None,
    game_state: dict[str, Any] | None = None,
    log_path: Path,
    lock: threading.Lock,
) -> tuple[bytes, dict[str, Any] | None, str | None]:
    response = b""
    response_candidate: dict[str, Any] | None = None
    response_wire_key: str | None = None
    endpoint_state = handshake_states.get(endpoint, HANDSHAKE_STATE_AWAITING_PROBE)

    if initial_probe and endpoint_state in {HANDSHAKE_STATE_AWAITING_PROBE, HANDSHAKE_STATE_AWAITING_RESPONSE}:
        token = data[36:68]
        cookie_a = hashlib.sha1(b"project-a-local-stateless-cookie-a" + token).digest()
        handshake_tokens[endpoint] = token
        handshake_cookies[endpoint] = cookie_a
        candidate = stateless_candidate_ares_packets(data)[1]
        response = candidate["wire_exact_clean_crc"]
        response_candidate = candidate
        response_wire_key = "wire_exact_clean_crc"
        handshake_states[endpoint] = HANDSHAKE_STATE_AWAITING_RESPONSE
        append_event(log_path, lock, {
            "event": "handshake_challenge_sent",
            "endpoint": endpoint,
            "state": HANDSHAKE_STATE_AWAITING_RESPONSE,
            "candidate": candidate["candidate"],
        })

    elif challenge_response and endpoint_state == HANDSHAKE_STATE_AWAITING_RESPONSE:
        token = handshake_tokens.get(endpoint, b"\x00" * 32)
        cookie_a = handshake_cookies.get(endpoint, b"\x00" * 20)
        if handshake_final_sequence is not None:
            _send_final_ack_candidates(
                sock=sock,
                addr=addr,
                endpoint=endpoint,
                token=token,
                cookie_a=cookie_a,
                challenge_response_packet=data,
                handshake_final_sequence=handshake_final_sequence,
                log_path=log_path,
                lock=lock,
                event_name="handshake_final_candidate",
            )
        else:
            ack = make_handshake_ack_74(token, cookie_a)
            try:
                sock.sendto(ack, addr)
                append_event(log_path, lock, {
                    "event": "handshake_ack_sent",
                    "endpoint": endpoint,
                    "state": HANDSHAKE_STATE_CONNECTED,
                    "ack_hex": ack.hex(),
                    "ack_length": len(ack),
                })
            except OSError as exc:
                append_event(log_path, lock, {"event": "handshake_ack_error", "endpoint": endpoint, "error": repr(exc)})
            ares_ack_payload = make_stateless_component_payload(True, False, 1, cookie_a)
            ares_ack = make_ares_frame_packet(ares_ack_payload, stateless_component_bit_count(), crc_includes_marker=False)
            try:
                sock.sendto(ares_ack, addr)
                append_event(log_path, lock, {
                    "event": "handshake_ares_ack_sent",
                    "endpoint": endpoint,
                    "ares_ack_hex": ares_ack.hex(),
                    "ares_ack_length": len(ares_ack),
                })
            except OSError as exc:
                append_event(log_path, lock, {"event": "handshake_ares_ack_error", "endpoint": endpoint, "error": repr(exc)})
        handshake_states[endpoint] = HANDSHAKE_STATE_CONNECTED

    elif challenge_response and endpoint_state == HANDSHAKE_STATE_CONNECTED and handshake_final_sequence is not None:
        append_event(log_path, lock, {
            "event": "handshake_post_final_client_packet",
            "endpoint": endpoint,
            "u32_at_8": challenge_response.get("u32_at_8"),
            "selector_at_10": challenge_response.get("selector_at_10"),
            "component_payload_12_32_hex": challenge_response.get("component_payload_12_32_hex"),
            "bit_count_at_32": challenge_response.get("bit_count_at_32"),
            "payload_hex": challenge_response.get("payload_hex"),
        })
        if challenge_response.get("u32_at_8") == 0x00050019 and challenge_response.get("bit_count_at_32") == 299:
            append_event(log_path, lock, {
                "event": "handshake_selector5_final_ack_seen",
                "endpoint": endpoint,
                "note": "client reached post-final selector 5; no raw74 adaptive reply sent",
            })
            seeds = _selector5_protected_seeds()
            if seeds:
                map_url = (game_state or {}).get("map", "/Game/Maps/Ascent/Ascent")
                game_mode = _ue_game_mode_for_welcome(game_state)
                welcome_payload = _ares_payload_from_packet(build_welcome_response(map_url, game_mode))
                login_payload = _ares_payload_from_packet(build_login_complete())
                for seed in seeds:
                    sent_key = (endpoint, seed)
                    if sent_key in _SELECTOR5_PROTECTED_SENT:
                        continue
                    _SELECTOR5_PROTECTED_SENT.add(sent_key)
                    for message_name, payload in (("welcome", welcome_payload), ("login_complete", login_payload)):
                        packet = make_ares_protected_frame_packet(payload, seed)
                        try:
                            sock.sendto(packet, addr)
                            append_event(log_path, lock, {
                                "event": "selector5_protected_control_sent",
                                "endpoint": endpoint,
                                "message": message_name,
                                "seed": seed,
                                "length": len(packet),
                                "hex_preview": packet[:48].hex(),
                            })
                        except OSError as exc:
                            append_event(log_path, lock, {
                                "event": "selector5_protected_control_error",
                                "endpoint": endpoint,
                                "message": message_name,
                                "seed": seed,
                                "error": repr(exc),
                            })

    elif initial_probe and endpoint_state == HANDSHAKE_STATE_CONNECTED:
        token = data[36:68]
        cookie_a = hashlib.sha1(b"project-a-local-stateless-cookie-a" + token).digest()
        handshake_tokens[endpoint] = token
        handshake_cookies[endpoint] = cookie_a
        candidate = stateless_candidate_ares_packets(data)[1]
        response = candidate["wire_exact_clean_crc"]
        response_candidate = candidate
        response_wire_key = "wire_exact_clean_crc"
        handshake_states[endpoint] = HANDSHAKE_STATE_AWAITING_RESPONSE
        append_event(log_path, lock, {
            "event": "handshake_reset_challenge_sent",
            "endpoint": endpoint,
            "state": HANDSHAKE_STATE_AWAITING_RESPONSE,
        })

    elif endpoint_state == HANDSHAKE_STATE_CONNECTED:
        if control_handlers is not None and not protected_packet and not _is_valid_unprotected_ares_frame(data):
            append_event(log_path, lock, {
                "event": "ue4_control_blocked_missing_ares_protection",
                "endpoint": endpoint,
                "length": len(data),
                "first32_hex": data[:32].hex(),
                "note": "post-handshake packet is neither known protected packet nor CRC-valid Ares frame; no bare UE control reply sent",
            })

        # Route only packets that at least satisfy a known post-handshake wrapper shape.
        elif control_handlers is not None:
            if endpoint not in control_handlers:
                # Create a new handler for this endpoint
                map_url = (game_state or {}).get("map", "/Game/Maps/Ascent/Ascent")
                game_mode = _ue_game_mode_for_welcome(game_state)
                control_handlers[endpoint] = UE4ControlChannelHandler(
                    map_url=map_url,
                    game_mode=game_mode,
                )
                append_event(log_path, lock, {
                    "event": "ue4_control_channel_created",
                    "endpoint": endpoint,
                    "map_url": map_url,
                    "game_mode": game_mode,
                })

            handler = control_handlers[endpoint]
            handler_input = data
            unwrapped_protected: dict[str, Any] | None = None
            if protected_packet:
                unwrapped_protected = unwrap_ares_protected_payload(
                    bytes.fromhex(protected_packet["protected_payload_hex"]),
                    _protected_seed_candidates(protected_packet),
                )
                if unwrapped_protected:
                    handler_input = unwrapped_protected["frame"]
                append_event(log_path, lock, {
                    "event": "ares_protected_unwrap_attempt",
                    "endpoint": endpoint,
                    "ok": bool(unwrapped_protected),
                    "seed": unwrapped_protected.get("seed") if unwrapped_protected else None,
                    "dropped_marker": unwrapped_protected.get("dropped_marker") if unwrapped_protected else None,
                    "frame_length": unwrapped_protected.get("frame_length") if unwrapped_protected else None,
                    "declared_length": unwrapped_protected.get("declared_length") if unwrapped_protected else None,
                })
                if not unwrapped_protected:
                    append_event(log_path, lock, {
                        "event": "ue4_control_blocked_unwrapped_protected_missing",
                        "endpoint": endpoint,
                        "counter": protected_packet.get("ares_counter_u32"),
                        "protected_payload_length": protected_packet.get("protected_payload_length"),
                        "note": "protected client payload did not unwrap to a CRC-valid Ares frame; no guessed UE reply sent",
                    })
                    return response, response_candidate, response_wire_key

            ue4_responses = handler.handle_packet(handler_input)
            for ue4_pkt in ue4_responses:
                outgoing_packets: list[tuple[bytes, int | None]] = [(ue4_pkt, None)]
                if protected_packet:
                    seeds = _protected_reply_seeds()
                    payload = _ares_payload_from_packet(ue4_pkt)
                    if seeds and payload:
                        outgoing_packets = [
                            (make_ares_protected_frame_packet(payload, seed), seed)
                            for seed in seeds
                        ]
                for outgoing_pkt, protected_seed in outgoing_packets:
                    try:
                        sock.sendto(outgoing_pkt, addr)
                        append_event(log_path, lock, {
                            "event": "ue4_control_packet_sent",
                            "endpoint": endpoint,
                            "state": handler.state,
                            "protected_seed": protected_seed,
                            "packet_length": len(outgoing_pkt),
                            "packet_hex_preview": outgoing_pkt[:32].hex(),
                        })
                    except OSError as exc:
                        append_event(log_path, lock, {
                            "event": "ue4_control_packet_error",
                            "endpoint": endpoint,
                            "protected_seed": protected_seed,
                            "error": repr(exc),
                        })

        elif protected_packet:
            keepalive = bytearray(28)
            counter = (protected_packet["ares_counter_u32"] + 1) & 0xFFFFFFFF
            keepalive[8:12] = counter.to_bytes(4, "little")
            keepalive[12:] = b"\x00" * 16
            try:
                sock.sendto(bytes(keepalive), addr)
                append_event(log_path, lock, {
                    "event": "handshake_keepalive_sent",
                    "endpoint": endpoint,
                    "counter": counter,
                })
            except OSError as exc:
                append_event(log_path, lock, {"event": "handshake_keepalive_error", "endpoint": endpoint, "error": repr(exc)})
        elif len(data) >= 6 and not initial_probe and not challenge_response:
            ares_frame = analyze_ares_frame(data)
            if ares_frame and ares_frame.get("checksum_ok"):
                echo_payload = data[6:6 + ares_frame["declared_length"]]
                echo_response = make_ares_frame(echo_payload)
                echo_response = append_packet_handler_marker(echo_response)
                try:
                    sock.sendto(echo_response, addr)
                    append_event(log_path, lock, {
                        "event": "handshake_echo_sent",
                        "endpoint": endpoint,
                        "echo_length": len(echo_response),
                    })
                except OSError as exc:
                    append_event(log_path, lock, {"event": "handshake_echo_error", "endpoint": endpoint, "error": repr(exc)})
            else:
                ack_frame = append_packet_handler_marker(make_ares_frame(b"\x00"))
                try:
                    sock.sendto(ack_frame, addr)
                    append_event(log_path, lock, {
                        "event": "handshake_frame_ack_sent",
                        "endpoint": endpoint,
                        "frame_ack_hex": ack_frame.hex(),
                    })
                except OSError as exc:
                    append_event(log_path, lock, {"event": "handshake_frame_ack_error", "endpoint": endpoint, "error": repr(exc)})

    return response, response_candidate, response_wire_key
