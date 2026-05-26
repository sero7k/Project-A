#!/usr/bin/env python3
"""UEGameServer entrypoint for the local Project A gameplay server.

This is a protocol-compatible server process, not an Unreal-built dedicated
server binary. The workspace does not contain a UE project or UnrealBuildTool,
so this entrypoint is the runnable target we evolve until the recovered client
can complete the Ares/PacketHandler boundary and load.
"""

from __future__ import annotations

import sys

from projecta.gameplay import socket as _socket


def _has_option(name: str) -> bool:
    prefix = f"{name}="
    return any(arg == name or arg.startswith(prefix) for arg in sys.argv[1:])


def main() -> int:
    if not _has_option("--udp-reply"):
        sys.argv.extend(["--udp-reply", "ares-handshake"])
    if not _has_option("--handshake-final-sequence"):
        sys.argv.extend(["--handshake-final-sequence", "68"])
    return _socket.main()


if __name__ == "__main__":
    raise SystemExit(main())
