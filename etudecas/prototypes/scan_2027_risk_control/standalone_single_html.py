#!/usr/bin/env python3
"""Compatibility entry point for the shared standalone HTML publisher.

Implementation: etudecas.visualization.standalone_html.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from etudecas.visualization import standalone_html as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    # Keep a single module object, including legacy private helpers and patches.
    sys.modules[__name__] = _implementation
