#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from projecta.gameplay.ares import analyze_ares_frame, stateless_candidate_ares_packets, stateless_final_ack_candidates
from projecta.gameplay.handshake import (
    HANDSHAKE_STATE_AWAITING_RESPONSE,
    HANDSHAKE_STATE_CONNECTED,
    handle_ares_handshake_packet,
)
from projecta.gameplay.packet_analysis import (
    analyze_client_challenge_response_74,
    analyze_client_initial_probe_74,
    analyze_udp_packet,
)


INITIAL_PROBE_74 = bytes.fromhex(
    "0000000000000000010000000000000000000000000000000000000000000000"
    "28010000c809cb91098b09cb693193a9b969a931c3316b099b81896989c1b199"
    "c931c3b9b111b3b10108"
)

CHALLENGE_RESPONSE_74 = bytes.fromhex(
    "00000000000000001900010000004006075d44ef407f2cf9a7134c2a9714d98f"
    "2d010000c809cb91098b09cb693193a9b969a931c3316b099b81896989c1b199"
    "c931c3b9b111b3b10108"
)

KNOWN_CLEAN_CHALLENGE_REPLY = bytes.fromhex(
    "8da0a13d1900010000004006075d44ef407f2cf9a7134c2a9714d98f95eb06"
)

KNOWN_DDOS_CLEAN_CHALLENGE_REPLY = b"\x00" * 8 + KNOWN_CLEAN_CHALLENGE_REPLY


def test_decodes_project_a_initial_probe_fixture():
    decoded = analyze_client_initial_probe_74(INITIAL_PROBE_74)

    assert decoded is not None
    assert decoded["kind"] == "project_a_client_initial_probe_74"
    assert decoded["payload_bit_count_at_32"] == 296
    assert decoded["client_token_length"] == 32
    assert decoded["trailer_hex"] == "b111b3b10108"
    assert analyze_udp_packet(INITIAL_PROBE_74)["project_a_74_byte_probe_candidate"] is True


def test_decodes_project_a_challenge_response_fixture():
    decoded = analyze_client_challenge_response_74(CHALLENGE_RESPONSE_74)

    assert decoded is not None
    assert decoded["kind"] == "project_a_client_challenge_response_74"
    assert decoded["payload_byte_length"] == 25
    assert decoded["u32_at_8"] == 65561
    assert decoded["bit_count_at_32"] == 301
    assert decoded["payload_hex"] == INITIAL_PROBE_74[36:61].hex()


def test_known_stateless_reply_fixture_is_stable():
    candidates = stateless_candidate_ares_packets(INITIAL_PROBE_74)
    candidate = candidates[1]
    reply = candidate["wire_exact_clean_crc"]

    assert candidate["candidate"] == "stateless-bit-f10-u0-c20"
    assert candidate["payload_bit_count"] == 194
    assert reply == KNOWN_CLEAN_CHALLENGE_REPLY
    assert len(reply) == 31
    assert candidate["wire_ddos_exact_clean_crc"] == KNOWN_DDOS_CLEAN_CHALLENGE_REPLY
    assert len(candidate["wire_ddos_exact_clean_crc"]) == 39

    frame = analyze_ares_frame(reply)
    assert frame is not None
    assert frame["length_ok"] is True
    # This is the currently reproduced wire shape, not proof that the client
    # accepts the packet-handler marker/checksum combination.
    assert frame["checksum_ok"] is False


def test_final_ack_candidates_are_stable_and_selectable():
    candidates = stateless_final_ack_candidates(INITIAL_PROBE_74[36:68], CHALLENGE_RESPONSE_74)

    # The generator intentionally grows as new protocol-lab ACK variants are
    # added; keep this pinned so accidental candidate churn is still visible.
    assert len(candidates) == 87
    assert candidates[0]["candidate"] == "raw74-final-bit-f10-u1-cookie-a-u2-b303"
    assert candidates[0]["wire_key"] == "raw74"
    assert len(candidates[0]["wire"]) == 74
    assert candidates[0]["wire"][8:12] == (2).to_bytes(4, "little")
    assert candidates[0]["wire"][32:36] == (303).to_bytes(4, "little")

    assert candidates[2]["candidate"] == "ares-clean-final-bit-f10-u1-cookie-a"
    assert candidates[2]["wire_key"] == "wire_exact_clean_crc"
    assert candidates[2]["wire"].hex() == "76ea1cc61900050000004006075d44ef407f2cf9a7134c2a9714d98f95eb06"
    assert candidates[2]["wire_ddos_key"] == "wire_ddos_exact_clean_crc"
    assert candidates[2]["wire_ddos"] == b"\x00" * 8 + candidates[2]["wire"]

    assert candidates[52]["candidate"] == "ares-clean-final-bit-f11-u0-cookie-a"
    assert candidates[52]["wire"].hex() == "d086c7ad1900030000004006075d44ef407f2cf9a7134c2a9714d98f95eb06"
    assert candidates[52]["wire_ddos"] == b"\x00" * 8 + candidates[52]["wire"]

    assert candidates[58]["candidate"] == "raw74-stateless-selector-03-response-cookie-b301-tail"
    assert candidates[58]["wire_key"] == "raw74_stateless"
    assert candidates[58]["wire"][8:12] == (0x00030019).to_bytes(4, "little")
    assert candidates[58]["wire"][12:32] == CHALLENGE_RESPONSE_74[12:32]
    assert candidates[58]["wire"][32:36] == (301).to_bytes(4, "little")
    assert candidates[58]["wire"][36:74] == CHALLENGE_RESPONSE_74[36:74]


class _FakeSocket:
    def __init__(self):
        self.sent = []

    def sendto(self, packet, addr):
        self.sent.append((packet, addr))


def test_connected_initial_probe_resets_handshake_instead_of_ue4_dispatch(tmp_path):
    sock = _FakeSocket()
    states = {"127.0.0.1:7777": HANDSHAKE_STATE_CONNECTED}
    tokens = {}
    cookies = {}
    initial_probe = analyze_client_initial_probe_74(INITIAL_PROBE_74)

    response, candidate, wire_key = handle_ares_handshake_packet(
        sock=sock,
        addr=("127.0.0.1", 7777),
        endpoint="127.0.0.1:7777",
        data=INITIAL_PROBE_74,
        initial_probe=initial_probe,
        challenge_response=None,
        protected_packet=None,
        handshake_states=states,
        handshake_tokens=tokens,
        handshake_cookies=cookies,
        handshake_final_sequence=[58],
        control_handlers={},
        game_state={},
        log_path=tmp_path / "events.jsonl",
        lock=__import__("threading").Lock(),
    )

    assert states["127.0.0.1:7777"] == HANDSHAKE_STATE_AWAITING_RESPONSE
    assert candidate["candidate"] == "stateless-bit-f10-u0-c20"
    assert wire_key == "wire_exact_clean_crc"
    assert response
    assert not sock.sent
