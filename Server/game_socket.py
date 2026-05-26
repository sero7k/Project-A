#!/usr/bin/env python3
"""Compatibility wrapper for the local game-port observer."""

from __future__ import annotations

import sys

from projecta.gameplay import socket as _socket


if __name__ == "__main__":
    raise SystemExit(_socket.main())
else:
    sys.modules[__name__] = _socket
