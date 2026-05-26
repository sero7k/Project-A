#!/usr/bin/env python3
"""Compatibility facade for the local game-port observer."""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    script_dir = Path(__file__).resolve().parent
    if sys.path and Path(sys.path[0]).resolve() == script_dir:
        sys.path.pop(0)
    sys.path.insert(0, str(script_dir.parents[1]))
    __package__ = "projecta.gameplay"

from .ares import (
    BitWriter,
    analyze_ares_frame,
    append_packet_handler_marker,
    append_packet_handler_marker_at_bit,
    ares_crc32,
    make_ares_frame,
    make_ares_frame_packet,
    make_handshake_ack_74,
    make_raw_handshake_packet_74,
    make_raw_stateless_packet_74_from_payload,
    make_stateless_component_payload,
    make_stateless_component_payload_byte_aligned,
    make_ue_stateless_challenge_ack,
    make_ue_stateless_component_payload,
    stateless_candidate_ares_packets,
    stateless_component_bit_count,
    stateless_final_ack_candidates,
)
from .cli import main
from .event_log import append_event
from .handshake import (
    HANDSHAKE_STATE_AWAITING_PROBE,
    HANDSHAKE_STATE_AWAITING_RESPONSE,
    HANDSHAKE_STATE_CONNECTED,
)
from .observers import (
    tcp_observer,
    udp_observer,
)
from .packet_analysis import (
    analyze_client_challenge_response_74,
    analyze_client_initial_probe_74,
    analyze_protected_game_packet,
    analyze_udp_packet,
)
from .ue_control_channel import (
    UE4ControlChannelHandler,
    ConnectionState,
    NMT,
    build_login_complete,
    build_nul_ack,
    build_welcome_response,
    detect_control_bunch,
    parse_bunch_header,
)

__all__ = [
    "BitWriter",
    "ConnectionState",
    "HANDSHAKE_STATE_AWAITING_PROBE",
    "HANDSHAKE_STATE_AWAITING_RESPONSE",
    "HANDSHAKE_STATE_CONNECTED",
    "NMT",
    "UE4ControlChannelHandler",
    "analyze_ares_frame",
    "analyze_client_challenge_response_74",
    "analyze_client_initial_probe_74",
    "analyze_protected_game_packet",
    "analyze_udp_packet",
    "append_event",
    "append_packet_handler_marker",
    "append_packet_handler_marker_at_bit",
    "ares_crc32",
    "build_login_complete",
    "build_nul_ack",
    "build_welcome_response",
    "detect_control_bunch",
    "main",
    "make_ares_frame",
    "make_ares_frame_packet",
    "make_handshake_ack_74",
    "make_raw_handshake_packet_74",
    "make_raw_stateless_packet_74_from_payload",
    "make_stateless_component_payload",
    "make_stateless_component_payload_byte_aligned",
    "make_ue_stateless_challenge_ack",
    "make_ue_stateless_component_payload",
    "parse_bunch_header",
    "stateless_candidate_ares_packets",
    "stateless_component_bit_count",
    "stateless_final_ack_candidates",
    "tcp_observer",
    "udp_observer",
]


if __name__ == "__main__":
    raise SystemExit(main())
