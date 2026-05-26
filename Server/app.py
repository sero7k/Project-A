#!/usr/bin/env python3
"""Compatibility wrapper for the Project A control-plane app."""

from __future__ import annotations

import sys

from projecta.control_plane import app as _app


if __name__ == "__main__":
    _app.main()
else:
    sys.modules[__name__] = _app
