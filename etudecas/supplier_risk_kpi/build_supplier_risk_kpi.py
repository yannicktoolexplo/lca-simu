#!/usr/bin/env python3
"""Compatibility wrapper for the supplier criticality builder.

Canonical implementation:
    etudecas.risk.supplier_criticality.build_supplier_criticality
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from etudecas.risk.supplier_criticality.build_supplier_criticality import main
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from etudecas.risk.supplier_criticality.build_supplier_criticality import main


if __name__ == "__main__":
    main()

