"""Minimal UE4 control channel protocol handler.

After the Ares handshake completes and the PacketHandler layer is established,
UE4 game packets arrive as 'bunches' on channels. Channel 0 is the control channel
which handles the login sequence.

This module provides just enough to get the client past the login gate and into
a loading screen. It does NOT implement full actor replication.

Key UE4 network concepts:
- Packets contain one or more Bunches
- Each Bunch has: bOpen, bClose, bReliable, ChIndex, ChSequence, data
- Channel 0 (Control) handles: Hello, Welcome, Login, Challenge
- The server must ack reliable bunches

UE4 Control Channel Message Flow:
1. Client sends NMT_Hello (with encryption token, network version)
2. Server responds NMT_Welcome (map URL, game mode, redirect URL)
3. Client sends NMT_Login (URL with player options, UniqueID, OnlinePlatformName)
4. Server responds NMT_Welcome or NMT_Login (acknowledged)
5. Server calls ClientLoginComplete on the PlayerController

For this VALORANT (Ares) build:
- ServerLoginPlayer is the login RPC
- ClientLoginComplete is the acknowledgement
- The map URL format is: /Game/Maps/Ascent/Ascent
"""

from __future__ import annotations

import struct
import time
from enum import IntEnum
from typing import Any

from .ares import BitWriter, ares_crc32, make_ares_frame, append_packet_handler_marker


# ---------------------------------------------------------------------------
# UE4 Control Message Types (NMT = Net Message Type)
# ---------------------------------------------------------------------------

class NMT(IntEnum):
    """UE4 control channel message types."""
    Hello = 0
    Welcome = 1
    Upgrade = 2
    Challenge = 3
    Login = 4
    Failure = 5
    Join = 9
    JoinSplit = 10
    Skip = 12
    Abort = 13
    PCSwap = 15
    ActorChannelFailure = 16
    DebugText = 17
    NetGUIDAssign = 18
    SecurityViolation = 19
    GameSpecific = 20


# ---------------------------------------------------------------------------
# Connection states for the UE4 login sequence
# ---------------------------------------------------------------------------

class ConnectionState:
    PRE_LOGIN = "pre_login"
    LOGGING_IN = "logging_in"
    LOGGED_IN = "logged_in"
    MAP_LOADED = "map_loaded"


# ---------------------------------------------------------------------------
# UE4 Bunch Header Bits (UE 4.22 layout)
#
# UE4 bunch headers are bit-packed. The minimal layout is:
#   1 bit  - bHasControlFlags (bOpen || bClose)
#   if bHasControlFlags:
#       1 bit  - bOpen
#       1 bit  - bClose
#       if bClose: SerializeInt(CloseReason, EChannelCloseReason::MAX)
#   1 bit  - bIsReplicationPaused
#   1 bit  - bReliable
#   variable - ChIndex (SerializeIntPacked)
#   1 bit  - bHasPackageMapExports
#   1 bit  - bHasMustBeMappedGUIDs
#   1 bit  - bPartial
#   if bReliable:
#       WriteIntWrapped(ChSequence, MAX_CHSEQUENCE)
#   if bPartial:
#       1 bit - bPartialInitial
#       1 bit - bPartialFinal
#   if bReliable || bOpen:
#       StaticSerializeName(ChName)
#   variable - BunchDataBits (WriteIntWrapped, MaxPacket * 8)
#   BunchDataBits bits - Bunch payload
# ---------------------------------------------------------------------------

# Channel types
CHTYPE_CONTROL = 1
CHTYPE_ACTOR = 2
CHTYPE_VOICE = 4

MAX_CHSEQUENCE = 1024
MAX_PACKET_SIZE = 1024
MAX_PACKET_BITS = MAX_PACKET_SIZE * 8
NAME_CONTROL_INDEX = 255

# Default settings
DEFAULT_MAP_URL = "/Game/Maps/Poveglia/Range"
DEFAULT_GAME_MODE = "/Script/ShooterGame.ShooterGameMode"

# Sequence tracking
INITIAL_OUTGOING_SEQUENCE = 1


class BitReader:
    """Simple bit-level reader for parsing UE4 bit-packed headers."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._bit_pos = 0

    @property
    def bits_remaining(self) -> int:
        return len(self._data) * 8 - self._bit_pos

    @property
    def bit_pos(self) -> int:
        return self._bit_pos

    def read_bit(self) -> bool:
        if self._bit_pos >= len(self._data) * 8:
            return False
        byte_index = self._bit_pos >> 3
        bit_index = self._bit_pos & 7
        self._bit_pos += 1
        return bool(self._data[byte_index] & (1 << bit_index))

    def read_bits(self, count: int) -> int:
        """Read `count` bits as an unsigned integer (LSB first)."""
        value = 0
        for i in range(count):
            if self.read_bit():
                value |= (1 << i)
        return value

    def read_int_wrapped(self, value_max: int) -> int:
        """Read UE4 SerializeInt/WriteIntWrapped encoding."""
        value = 0
        mask = 1
        while value + mask < value_max and mask:
            if self.read_bit():
                value |= mask
            mask <<= 1
        return value

    def read_int_packed(self) -> int:
        """Read a UE4 variable-length packed integer (SerializeIntPacked).

        UE4 stores continuation in bit 0 and seven payload bits in bits 1..7.
        """
        value = 0
        shift = 0
        for _ in range(5):
            byte_val = self.read_bits(8)
            value |= (byte_val >> 1) << shift
            if not (byte_val & 1):
                break
            shift += 7
        return value

    def read_bytes(self, count: int) -> bytes:
        """Read `count` bytes (8 bits each)."""
        result = bytearray()
        for _ in range(count):
            result.append(self.read_bits(8))
        return bytes(result)


def parse_bunch_header(data: bytes) -> dict[str, Any] | None:
    """Parse a UE4 bunch header from raw packet data.

    Returns a dict with parsed fields, or None if data is too short.
    This is a best-effort parser for the control channel case.
    """
    if len(data) < 4:
        return None

    reader = BitReader(data)
    result: dict[str, Any] = {}

    try:
        result["bHasControlFlags"] = reader.read_bit()
        result["bControl"] = result["bHasControlFlags"]
        result["bOpen"] = False
        result["bClose"] = False

        if result["bHasControlFlags"]:
            result["bOpen"] = reader.read_bit()
            result["bClose"] = reader.read_bit()
            if result["bClose"]:
                result["CloseReason"] = reader.read_int_wrapped(4)

        result["bIsReplicationPaused"] = reader.read_bit()
        result["bReliable"] = reader.read_bit()

        result["ChIndex"] = reader.read_int_packed()

        result["bHasPackageMapExports"] = reader.read_bit()
        result["bHasMustBeMappedGUIDs"] = reader.read_bit()
        result["bPartial"] = reader.read_bit()

        if result["bReliable"]:
            result["ChSequence"] = reader.read_int_wrapped(MAX_CHSEQUENCE)

        if result["bPartial"]:
            result["bPartialInitial"] = reader.read_bit()
            result["bPartialFinal"] = reader.read_bit()

        if result["bReliable"] or result["bOpen"]:
            result["ChName"] = _read_static_name(reader)
            if result["ChName"] == "Control":
                result["ChType"] = CHTYPE_CONTROL

        result["BunchDataBits"] = reader.read_int_wrapped(MAX_PACKET_BITS)
        result["header_bits_consumed"] = reader.bit_pos

        # Read bunch payload (up to available data)
        payload_bits = min(result["BunchDataBits"], reader.bits_remaining)
        payload_bytes_count = (payload_bits + 7) // 8
        if payload_bytes_count > 0 and reader.bits_remaining >= 8:
            result["payload_data"] = reader.read_bytes(min(payload_bytes_count, reader.bits_remaining // 8))
        else:
            result["payload_data"] = b""

    except (IndexError, ValueError):
        result["parse_error"] = True

    return result


def detect_control_bunch(data: bytes) -> dict[str, Any] | None:
    """Detect if an incoming packet contains a control channel bunch.

    Looks for channel 0, reliable, with control flag or open flag.
    This is a heuristic check for the first bunch in a packet.
    """
    header = parse_bunch_header(data)
    if header is None:
        return None

    # Control channel is channel 0
    if header.get("ChIndex") == 0:
        return header

    # Also check if bControl is set regardless of channel index (some builds)
    if header.get("bControl"):
        return header

    return None


def parse_control_message_type(payload: bytes) -> int | None:
    """Extract the NMT type byte from a control channel bunch payload.

    In UE4, control messages start with a uint8 message type.
    """
    if not payload or len(payload) < 1:
        return None
    return payload[0]


# ---------------------------------------------------------------------------
# Packet construction helpers
# ---------------------------------------------------------------------------

def _write_ue4_string(writer: BitWriter, s: str) -> None:
    """Write a UE4 FString to a BitWriter (length-prefixed, null-terminated)."""
    encoded = s.encode("utf-8") + b"\x00"
    length = len(encoded)
    # Write length as 32-bit int (includes null terminator)
    writer.write_bytes(length.to_bytes(4, "little"))
    writer.write_bytes(encoded)


def _write_int_wrapped(writer: BitWriter, value: int, value_max: int) -> None:
    """Write UE4 FBitWriter::WriteIntWrapped."""
    if value_max < 2:
        raise ValueError("value_max must be >= 2")
    mask = 1
    new_value = 0
    while new_value + mask < value_max and mask:
        writer.write_bit(bool(value & mask))
        if value & mask:
            new_value += mask
        mask <<= 1


def _write_int_packed(writer: BitWriter, value: int) -> None:
    """Write UE4 SerializeIntPacked (bit0 continuation, bits1..7 payload)."""
    value &= 0xFFFFFFFF
    while True:
        has_more = (value & ~0x7F) != 0
        byte_val = ((value & 0x7F) << 1) | (1 if has_more else 0)
        writer.write_bytes(bytes([byte_val]))
        value >>= 7
        if not has_more:
            break


def _write_static_name_control(writer: BitWriter) -> None:
    """Write UPackageMap::StaticSerializeName for NAME_Control."""
    writer.write_bit(True)  # hardcoded FName
    _write_int_packed(writer, NAME_CONTROL_INDEX)


def _read_static_name(reader: BitReader) -> str:
    """Read enough of StaticSerializeName to recognize NAME_Control."""
    if reader.read_bit():
        name_index = reader.read_int_packed()
        return "Control" if name_index == NAME_CONTROL_INDEX else f"HardcodedName({name_index})"

    # Non-hardcoded FString path. This is best-effort; control channel should
    # be hardcoded in normal UE4 traffic.
    length = reader.read_bits(32)
    if length <= 0 or length > 4096:
        return "NameString(?)"
    raw = reader.read_bytes(length)
    _number = reader.read_bits(32)
    return raw.rstrip(b"\x00").decode("utf-8", errors="replace")


def _write_bunch_header(
    writer: BitWriter,
    *,
    b_open: bool = False,
    b_close: bool = False,
    b_reliable: bool = True,
    ch_index: int = 0,
    ch_sequence: int = 0,
    bunch_data_bits: int = 0,
) -> None:
    """Write UE4.22 FOutBunch header."""
    writer.write_bit(b_open or b_close)
    if b_open or b_close:
        writer.write_bit(b_open)
        writer.write_bit(b_close)
        if b_close:
            _write_int_wrapped(writer, 0, 4)  # EChannelCloseReason::Destroyed

    writer.write_bit(False)  # bIsReplicationPaused
    writer.write_bit(b_reliable)
    _write_int_packed(writer, ch_index)
    writer.write_bit(False)  # bHasPackageMapExports
    writer.write_bit(False)  # bHasMustBeMappedGUIDs
    writer.write_bit(False)  # bPartial

    if b_reliable:
        _write_int_wrapped(writer, ch_sequence, MAX_CHSEQUENCE)

    if b_reliable or b_open:
        _write_static_name_control(writer)

    _write_int_wrapped(writer, bunch_data_bits, MAX_PACKET_BITS)


def _build_bunch_header(
    *,
    b_control: bool = False,
    b_open: bool = False,
    b_close: bool = False,
    b_reliable: bool = True,
    ch_index: int = 0,
    ch_sequence: int = 0,
    ch_type: int = CHTYPE_CONTROL,
    bunch_data_bits: int = 0,
) -> bytes:
    """Build a UE4 bunch header as bit-packed bytes."""
    _ = b_control, ch_type
    writer = BitWriter()
    _write_bunch_header(
        writer,
        b_open=b_open,
        b_close=b_close,
        b_reliable=b_reliable,
        ch_index=ch_index,
        ch_sequence=ch_sequence,
        bunch_data_bits=bunch_data_bits,
    )
    return writer.finish()


def build_welcome_response(map_url: str, game_mode: str = DEFAULT_GAME_MODE) -> bytes:
    """Build a UE4 NMT_Welcome control channel message as a complete packet.

    The Welcome message contains:
    - Message type (NMT_Welcome = 1)
    - Map URL (FString)
    - GameMode class path (FString)
    - Redirect URL (FString, empty for direct connection)

    Returns the complete wire-ready packet (Ares-framed with PacketHandler marker).
    """
    # Build the control message payload
    payload_writer = BitWriter()

    # NMT type byte
    payload_writer.write_bytes(bytes([NMT.Welcome]))

    # Map URL
    _write_ue4_string(payload_writer, map_url)

    # Game mode class
    _write_ue4_string(payload_writer, game_mode)

    # Redirect URL (empty)
    _write_ue4_string(payload_writer, "")

    payload_data = payload_writer.finish()
    payload_data_bits = payload_writer.bit_count

    combined_writer = BitWriter()
    _write_bunch_header(
        combined_writer,
        b_open=True,
        b_close=False,
        b_reliable=True,
        ch_index=0,
        ch_sequence=INITIAL_OUTGOING_SEQUENCE,
        bunch_data_bits=payload_data_bits,
    )
    combined_writer.write_bytes(payload_data)

    bunch_bytes = combined_writer.finish()

    # Wrap in Ares frame with PacketHandler marker
    return append_packet_handler_marker(make_ares_frame(bunch_bytes))


def build_login_complete() -> bytes:
    """Build a UE4 ClientLoginComplete acknowledgement packet.

    This is a minimal control message telling the client the login
    sequence is complete and it should proceed to load the map.

    Returns the complete wire-ready packet (Ares-framed with PacketHandler marker).
    """
    # Build control message payload - just the NMT type for Join acknowledgement
    # In VALORANT/Ares builds, ClientLoginComplete is sent as a GameSpecific
    # control message or a Join confirmation. We use NMT_Welcome pattern
    # followed by an NMT_Join-like message.
    payload_writer = BitWriter()

    # Use NMT_Join (9) as the login complete signal
    payload_writer.write_bytes(bytes([NMT.Join]))

    payload_data = payload_writer.finish()
    payload_data_bits = payload_writer.bit_count

    combined_writer = BitWriter()
    _write_bunch_header(
        combined_writer,
        b_open=False,
        b_close=False,
        b_reliable=True,
        ch_index=0,
        ch_sequence=INITIAL_OUTGOING_SEQUENCE + 1,
        bunch_data_bits=payload_data_bits,
    )
    combined_writer.write_bytes(payload_data)

    bunch_bytes = combined_writer.finish()

    return append_packet_handler_marker(make_ares_frame(bunch_bytes))


def build_nul_ack(out_ack_seq: int = 0) -> bytes:
    """Build a minimal NUL acknowledgement packet.

    UE4 connections require periodic acks to stay alive even when no
    bunches are pending. This is the simplest valid packet - just a
    sequence/ack header with no bunches.

    The ack header in UE4 is typically:
    - InAckSeq (sequence we've received up to)
    - Sent/received counters

    For a minimal keep-alive, we send a zero-payload Ares frame.
    """
    # Minimal ack: just an empty payload indicating "nothing new"
    # The Ares frame with empty payload acts as a NUL ack
    ack_data = struct.pack("<H", out_ack_seq & 0xFFFF)
    return append_packet_handler_marker(make_ares_frame(ack_data))


# ---------------------------------------------------------------------------
# Connection handler class
# ---------------------------------------------------------------------------

class UE4ControlChannelHandler:
    """Manages the UE4 control channel login sequence after Ares handshake.

    Tracks state through the login flow and generates appropriate responses.
    """

    def __init__(
        self,
        map_url: str = DEFAULT_MAP_URL,
        game_mode: str = DEFAULT_GAME_MODE,
    ) -> None:
        self.map_url = map_url
        self.game_mode = game_mode
        self.state = ConnectionState.PRE_LOGIN
        self.in_reliable_seq = 0  # last reliable sequence received
        self.out_reliable_seq = 0  # next reliable sequence to send
        self.out_ack_seq = 0  # outbound ack sequence counter
        self.last_activity = time.time()
        self.packets_received = 0
        self.packets_sent_log: list[dict[str, Any]] = []

    def handle_packet(self, data: bytes) -> list[bytes]:
        """Process an incoming game packet and return response packets.

        Args:
            data: Raw packet data (after Ares handshake, this is a game packet
                  that may contain UE4 bunches).

        Returns:
            List of response packets to send back. May be empty if no response
            is needed, or contain multiple packets (welcome + login complete).
        """
        self.packets_received += 1
        self.last_activity = time.time()
        responses: list[bytes] = []

        # Try to detect a control channel bunch
        # First strip the Ares frame if present
        payload = self._extract_payload(data)
        if payload is None:
            # Not a valid Ares frame, send a NUL ack to keep alive
            responses.append(build_nul_ack(self.out_ack_seq))
            self.out_ack_seq += 1
            return responses

        # Try to parse as a bunch
        bunch = detect_control_bunch(payload)

        if bunch is not None:
            responses.extend(self._handle_control_bunch(bunch))
        elif self.state == ConnectionState.PRE_LOGIN:
            # First non-handshake packet after connection - treat as Hello
            # Some builds send Hello implicitly as the first reliable packet
            responses.extend(self._send_welcome_sequence())
        else:
            # Regular packet in connected state - just ack
            responses.append(build_nul_ack(self.out_ack_seq))
            self.out_ack_seq += 1

        return responses

    def _extract_payload(self, data: bytes) -> bytes | None:
        """Extract payload from an Ares-framed packet."""
        if len(data) < 6:
            return None
        # Ares frame: 4 bytes CRC + 2 bytes length + payload
        declared_length = int.from_bytes(data[4:6], "little")
        if declared_length > len(data) - 6:
            # Might not be Ares-framed, try treating raw
            return data
        payload = data[6:6 + declared_length]
        # Verify CRC
        received_crc = int.from_bytes(data[:4], "little")
        calculated_crc = ares_crc32(payload)
        if received_crc == calculated_crc:
            return payload
        # CRC mismatch - might be a different framing, return raw
        return data

    def _handle_control_bunch(self, bunch: dict[str, Any]) -> list[bytes]:
        """Handle a parsed control channel bunch based on current state."""
        responses: list[bytes] = []

        # Track reliable sequence
        if bunch.get("bReliable") and "ChSequence" in bunch:
            self.in_reliable_seq = max(self.in_reliable_seq, bunch["ChSequence"])

        # Determine the control message type from payload
        payload_data = bunch.get("payload_data", b"")
        msg_type = parse_control_message_type(payload_data)

        if msg_type == NMT.Hello or self.state == ConnectionState.PRE_LOGIN:
            # Client sent Hello -> respond with Welcome + LoginComplete
            responses.extend(self._send_welcome_sequence())

        elif msg_type == NMT.Login:
            # Client sent Login -> respond with LoginComplete
            if self.state == ConnectionState.LOGGING_IN:
                responses.extend(self._send_login_complete())

        elif msg_type == NMT.Join:
            # Client acknowledged join
            self.state = ConnectionState.MAP_LOADED
            responses.append(build_nul_ack(self.out_ack_seq))
            self.out_ack_seq += 1

        else:
            # Unknown or unhandled message - ack it
            responses.append(build_nul_ack(self.out_ack_seq))
            self.out_ack_seq += 1

        return responses

    def _send_welcome_sequence(self) -> list[bytes]:
        """Generate the full welcome sequence: Welcome message + LoginComplete."""
        self.state = ConnectionState.LOGGING_IN
        self.out_reliable_seq += 1

        responses: list[bytes] = []

        # Send Welcome with map URL
        welcome = build_welcome_response(self.map_url, self.game_mode)
        responses.append(welcome)
        self._log_sent("NMT_Welcome", welcome)

        # Send LoginComplete
        responses.extend(self._send_login_complete())

        return responses

    def _send_login_complete(self) -> list[bytes]:
        """Generate the login complete message."""
        self.state = ConnectionState.LOGGED_IN
        self.out_reliable_seq += 1

        login_complete = build_login_complete()
        self._log_sent("NMT_Join/LoginComplete", login_complete)

        return [login_complete]

    def _log_sent(self, label: str, packet: bytes) -> None:
        """Track sent packets for diagnostics."""
        self.packets_sent_log.append({
            "label": label,
            "time": time.time(),
            "length": len(packet),
            "hex_preview": packet[:32].hex(),
            "state": self.state,
        })

    def get_status(self) -> dict[str, Any]:
        """Return current handler status for diagnostics."""
        return {
            "state": self.state,
            "in_reliable_seq": self.in_reliable_seq,
            "out_reliable_seq": self.out_reliable_seq,
            "out_ack_seq": self.out_ack_seq,
            "packets_received": self.packets_received,
            "packets_sent_count": len(self.packets_sent_log),
            "last_activity": self.last_activity,
        }
