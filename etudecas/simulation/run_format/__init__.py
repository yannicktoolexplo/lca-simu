"""Generic simulation run package helpers.

The package exported by this module is intentionally independent from the map
HTML and from the historical CSV names.  It provides a stable contract for
viewers, diagnostics and future APIs while keeping bulky time-series in their
native CSV files by default.
"""

from etudecas.simulation.run_format.exporter import export_run_package
from etudecas.simulation.run_format.loader import RunPackage, load_run_package
from etudecas.simulation.run_format.validator import validate_run_package

__all__ = ["RunPackage", "export_run_package", "load_run_package", "validate_run_package"]
