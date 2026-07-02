#!/usr/bin/env python3
"""Compatibility wrapper for the supply-chain world map builder.

Canonical implementation:
    etudecas.visualization.maps.build_supplychain_worldmap
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from etudecas.visualization.maps.build_supplychain_worldmap import *  # noqa: F401,F403
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from etudecas.visualization.maps.build_supplychain_worldmap import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
