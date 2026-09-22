"""Compatibility entrypoint for etudecas.simulation.analysis.report_finished_goods_stock_value.

The canonical module also backs imports through this historical path, including
its constants and helpers. Direct execution delegates to the same CLI.
"""
from pathlib import Path as _Path
import sys as _sys

_repo_root = _Path(__file__).resolve().parents[3]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

from etudecas.simulation.analysis import report_finished_goods_stock_value as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    _sys.modules[__name__] = _implementation
