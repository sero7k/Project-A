"""UDP reply logging helpers for gameplay observer modes."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Any

from .event_log import append_event


def send_udp_reply(
    sock: socket.socket,
    addr: tuple[str, int],
    log_path: Path,
    lock: threading.Lock,
    endpoint: str,
    response: bytes,
    reply_mode: str,
    response_candidate: dict[str, Any] | None = None,
    response_wire_key: str | None = None,
) -> None:
    try:
        sent = sock.sendto(response, addr)
        append_event(
            log_path,
            lock,
            {
                "event": "udp_reply",
                "to_host": addr[0],
                "to_port": addr[1],
                "endpoint": endpoint,
                "length": sent,
                "hex": response.hex(),
                "reply_mode": reply_mode,
                "candidate": response_candidate["candidate"] if response_candidate else None,
                "candidate_payload_hex": response_candidate["payload_hex"] if response_candidate else None,
                "candidate_payload_bit_count": response_candidate["payload_bit_count"] if response_candidate else None,
                "wire_key": response_wire_key,
            },
        )
    except OSError as exc:
        append_event(log_path, lock, {"event": "udp_reply_error", "endpoint": endpoint, "error": repr(exc)})


def send_stateless_candidate_repeat(
    sock: socket.socket,
    addr: tuple[str, int],
    log_path: Path,
    lock: threading.Lock,
    endpoint: str,
    reply_mode: str,
    candidate: dict[str, Any],
    repeat_count: int = 9,
) -> None:
    for repeat_index in range(repeat_count):
        candidate_response = candidate["wire"]
        try:
            sent = sock.sendto(candidate_response, addr)
            append_event(
                log_path,
                lock,
                {
                    "event": "udp_reply",
                    "to_host": addr[0],
                    "to_port": addr[1],
                    "endpoint": endpoint,
                    "length": sent,
                    "hex": candidate_response.hex(),
                    "reply_mode": reply_mode,
                    "candidate": candidate["candidate"],
                    "candidate_payload_hex": candidate["payload_hex"],
                    "candidate_payload_bit_count": candidate["payload_bit_count"],
                    "repeat_index": repeat_index,
                    "wire_key": "wire",
                },
            )
            time.sleep(0.025)
        except OSError as exc:
            append_event(log_path, lock, {"event": "udp_reply_error", "endpoint": endpoint, "error": repr(exc), "candidate": candidate["candidate"]})


def send_stateless_candidate_sequence(
    sock: socket.socket,
    addr: tuple[str, int],
    log_path: Path,
    lock: threading.Lock,
    endpoint: str,
    reply_mode: str,
    candidates: list[dict[str, Any]],
    sequence: list[int],
) -> None:
    for sequence_index, candidate_index in enumerate(sequence):
        if candidate_index < 0 or candidate_index >= len(candidates):
            append_event(log_path, lock, {"event": "udp_reply_error", "endpoint": endpoint, "error": f"candidate index {candidate_index} is out of range"})
            continue
        candidate = candidates[candidate_index]
        candidate_response = candidate["wire"]
        try:
            sent = sock.sendto(candidate_response, addr)
            append_event(
                log_path,
                lock,
                {
                    "event": "udp_reply",
                    "to_host": addr[0],
                    "to_port": addr[1],
                    "endpoint": endpoint,
                    "length": sent,
                    "hex": candidate_response.hex(),
                    "reply_mode": reply_mode,
                    "candidate": candidate["candidate"],
                    "candidate_index": candidate_index,
                    "candidate_payload_hex": candidate["payload_hex"],
                    "candidate_payload_bit_count": candidate["payload_bit_count"],
                    "sequence_index": sequence_index,
                    "wire_key": "wire",
                },
            )
            time.sleep(0.025)
        except OSError as exc:
            append_event(log_path, lock, {"event": "udp_reply_error", "endpoint": endpoint, "error": repr(exc), "candidate": candidate["candidate"]})


def send_stateless_candidate_burst(
    sock: socket.socket,
    addr: tuple[str, int],
    log_path: Path,
    lock: threading.Lock,
    endpoint: str,
    reply_mode: str,
    candidates: list[dict[str, Any]],
) -> None:
    for candidate in candidates:
        candidate_response = candidate["wire"]
        try:
            sent = sock.sendto(candidate_response, addr)
            append_event(
                log_path,
                lock,
                {
                    "event": "udp_reply",
                    "to_host": addr[0],
                    "to_port": addr[1],
                    "endpoint": endpoint,
                    "length": sent,
                    "hex": candidate_response.hex(),
                    "reply_mode": reply_mode,
                    "candidate": candidate["candidate"],
                    "candidate_payload_hex": candidate["payload_hex"],
                    "candidate_payload_bit_count": candidate["payload_bit_count"],
                    "wire_key": "wire",
                },
            )
            time.sleep(0.025)
        except OSError as exc:
            append_event(log_path, lock, {"event": "udp_reply_error", "endpoint": endpoint, "error": repr(exc), "candidate": candidate["candidate"]})
