"""Stateful Ares handshake handling for the UDP observer."""

from __future__ import annotations

import hashlib
import socket
import threading
from pathlib import Path
from typing import Any

from .ares import (
    analyze_ares_frame,
    append_packet_handler_marker,
    make_ares_frame,
    make_ares_frame_packet,
    make_handshake_ack_74,
    make_stateless_component_payload,
    stateless_candidate_ares_packets,
    stateless_component_bit_count,
    stateless_final_ack_candidates,
)
from .event_log import append_event
from .ue_control_channel import UE4ControlChannelHandler


HANDSHAKE_STATE_AWAITING_PROBE = "awaiting_probe"
HANDSHAKE_STATE_AWAITING_RESPONSE = "awaiting_response"
HANDSHAKE_STATE_CONNECTED = "connected"


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
            "bit_count_at_32": challenge_response.get("bit_count_at_32"),
            "payload_hex": challenge_response.get("payload_hex"),
        })

    elif endpoint_state == HANDSHAKE_STATE_CONNECTED:
        # Route packets through UE4 control channel handler if available
        if control_handlers is not None:
            if endpoint not in control_handlers:
                # Create a new handler for this endpoint
                map_url = (game_state or {}).get("map", "/Game/Maps/Ascent/Ascent")
                game_mode = (game_state or {}).get("game_mode", "/Script/ShooterGame.ShooterGameMode")
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
            ue4_responses = handler.handle_packet(data)
            for ue4_pkt in ue4_responses:
                try:
                    sock.sendto(ue4_pkt, addr)
                    append_event(log_path, lock, {
                        "event": "ue4_control_packet_sent",
                        "endpoint": endpoint,
                        "state": handler.state,
                        "packet_length": len(ue4_pkt),
                        "packet_hex_preview": ue4_pkt[:32].hex(),
                    })
                except OSError as exc:
                    append_event(log_path, lock, {
                        "event": "ue4_control_packet_error",
                        "endpoint": endpoint,
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

    elif initial_probe and endpoint_state == HANDSHAKE_STATE_CONNECTED:
        handshake_states[endpoint] = HANDSHAKE_STATE_AWAITING_PROBE
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

    return response, response_candidate, response_wire_key
