"""TCP/UDP observer loops for the local game-port service."""

from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Any

from .ares import (
    analyze_ares_frame,
    append_packet_handler_marker,
    make_ares_frame,
    stateless_candidate_ares_packets,
)
from .event_log import append_event
from .handshake import (
    HANDSHAKE_STATE_AWAITING_PROBE,
    HANDSHAKE_STATE_AWAITING_RESPONSE,
    HANDSHAKE_STATE_CONNECTED,
    handle_ares_handshake_packet,
)
from .packet_analysis import (
    analyze_client_challenge_response_74,
    analyze_client_initial_probe_74,
    analyze_protected_game_packet,
    analyze_udp_packet,
)
from .ue_control_channel import UE4ControlChannelHandler
from .udp_replies import (
    send_stateless_candidate_burst,
    send_stateless_candidate_repeat,
    send_stateless_candidate_sequence,
    send_udp_reply,
)


def udp_observer(
    host: str,
    port: int,
    log_path: Path,
    lock: threading.Lock,
    stop: threading.Event,
    reply_mode: str = "none",
    reply_bytes: bytes = b"",
    stateless_sequence: list[int] | None = None,
    handshake_final_sequence: list[int] | None = None,
    game_state: dict[str, Any] | None = None,
) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.settimeout(0.25)
    append_event(log_path, lock, {"event": "udp_listening", "host": host, "port": port, "reply_mode": reply_mode})
    packet_counts: dict[str, int] = {}
    last_protected_counters: dict[str, int] = {}
    burst_replied_endpoints: set[str] = set()
    handshake_states: dict[str, str] = {}
    handshake_tokens: dict[str, bytes] = {}
    handshake_cookies: dict[str, bytes] = {}
    control_handlers: dict[str, UE4ControlChannelHandler] = {}
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError as exc:
            append_event(log_path, lock, {"event": "udp_error", "error": repr(exc)})
            break
        endpoint = f"{addr[0]}:{addr[1]}"
        packet_counts[endpoint] = packet_counts.get(endpoint, 0) + 1
        initial_probe = analyze_client_initial_probe_74(data)
        challenge_response = analyze_client_challenge_response_74(data)
        protected_packet = analyze_protected_game_packet(data, last_protected_counters.get(endpoint))
        if protected_packet is not None:
            last_protected_counters[endpoint] = protected_packet["ares_counter_u32"]
        append_event(
            log_path,
            lock,
            {
                "event": "udp_packet",
                "from_host": addr[0],
                "from_port": addr[1],
                "endpoint": endpoint,
                "packet_index": packet_counts[endpoint],
                "length": len(data),
                "first64_hex": data[:64].hex(),
                "hex": data.hex(),
                "ares_frame": None if initial_probe or protected_packet or challenge_response else analyze_ares_frame(data),
                "client_initial_probe_74": initial_probe,
                "client_challenge_response_74": challenge_response,
                "protected_game_packet": protected_packet,
                "udp_analysis": analyze_udp_packet(data),
                "handshake_state": handshake_states.get(endpoint),
            },
        )
        response = b""
        response_candidate: dict[str, Any] | None = None
        response_wire_key: str | None = None

        if reply_mode == "ares-handshake":
            response, response_candidate, response_wire_key = handle_ares_handshake_packet(
                sock=sock,
                addr=addr,
                endpoint=endpoint,
                data=data,
                initial_probe=initial_probe,
                challenge_response=challenge_response,
                protected_packet=protected_packet,
                handshake_states=handshake_states,
                handshake_tokens=handshake_tokens,
                handshake_cookies=handshake_cookies,
                handshake_final_sequence=handshake_final_sequence,
                control_handlers=control_handlers,
                game_state=game_state,
                log_path=log_path,
                lock=lock,
            )

        elif reply_mode == "echo":
            response = data
        elif reply_mode in {"hex", "ares-hex", "packet-hex", "ares-packet-hex"}:
            response = reply_bytes
        elif reply_mode == "ares-empty-packet":
            response = append_packet_handler_marker(make_ares_frame(b""))
        elif reply_mode in {
            "ares-stateless-challenge",
            "ares-stateless-challenge-exact-clean",
            "ares-stateless-challenge-exact-marker",
        } and initial_probe and endpoint not in burst_replied_endpoints:
            burst_replied_endpoints.add(endpoint)
            candidate = stateless_candidate_ares_packets(data)[1]
            response_wire_key = {
                "ares-stateless-challenge": "wire",
                "ares-stateless-challenge-exact-clean": "wire_exact_clean_crc",
                "ares-stateless-challenge-exact-marker": "wire_exact_marker_crc",
            }[reply_mode]
            response = candidate[response_wire_key]
            response_candidate = candidate
        elif reply_mode == "ares-stateless-repeat" and initial_probe and endpoint not in burst_replied_endpoints:
            burst_replied_endpoints.add(endpoint)
            candidate = stateless_candidate_ares_packets(data)[1]
            send_stateless_candidate_repeat(sock, addr, log_path, lock, endpoint, reply_mode, candidate)
        elif reply_mode == "ares-stateless-bootstrap" and initial_probe and endpoint not in burst_replied_endpoints:
            burst_replied_endpoints.add(endpoint)
            candidates = stateless_candidate_ares_packets(data)
            send_stateless_candidate_sequence(sock, addr, log_path, lock, endpoint, reply_mode, candidates, [0, 1, 2, 3, 4, 5])
        elif reply_mode == "ares-stateless-sequence" and initial_probe and endpoint not in burst_replied_endpoints:
            burst_replied_endpoints.add(endpoint)
            candidates = stateless_candidate_ares_packets(data)
            sequence = stateless_sequence if stateless_sequence is not None else list(range(len(candidates)))
            send_stateless_candidate_sequence(sock, addr, log_path, lock, endpoint, reply_mode, candidates, sequence)
        elif reply_mode == "ares-stateless-burst" and initial_probe and endpoint not in burst_replied_endpoints:
            burst_replied_endpoints.add(endpoint)
            send_stateless_candidate_burst(sock, addr, log_path, lock, endpoint, reply_mode, stateless_candidate_ares_packets(data))
        if response:
            send_udp_reply(sock, addr, log_path, lock, endpoint, response, reply_mode, response_candidate, response_wire_key)
    sock.close()
    append_event(log_path, lock, {"event": "udp_stopped"})


def tcp_observer(host: str, port: int, log_path: Path, lock: threading.Lock, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(8)
    sock.settimeout(0.25)
    append_event(log_path, lock, {"event": "tcp_listening", "host": host, "port": port})
    while not stop.is_set():
        try:
            conn, addr = sock.accept()
        except socket.timeout:
            continue
        except OSError as exc:
            append_event(log_path, lock, {"event": "tcp_error", "error": repr(exc)})
            break
        with conn:
            conn.settimeout(0.5)
            try:
                data = conn.recv(4096)
            except socket.timeout:
                data = b""
            append_event(
                log_path,
                lock,
                {
                    "event": "tcp_connection",
                    "from_host": addr[0],
                    "from_port": addr[1],
                    "endpoint": f"{addr[0]}:{addr[1]}",
                    "length": len(data),
                    "first64_hex": data[:64].hex(),
                    "hex": data.hex(),
                },
            )
    sock.close()
    append_event(log_path, lock, {"event": "tcp_stopped"})
