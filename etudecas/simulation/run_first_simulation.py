#!/usr/bin/env python3
"""Compatibility wrapper for the simulation engine entrypoint.

Canonical implementation:
    etudecas.simulation.engine.run_first_simulation
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from etudecas.simulation.engine.run_first_simulation import *  # noqa: F401,F403
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from etudecas.simulation.engine.run_first_simulation import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
