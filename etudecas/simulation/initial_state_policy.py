"""Shared simulation startup-state policies.

The reference runs should start from the observed ERP/MRP snapshot at J0:
physical stocks from ``Stocks_MRP.xlsx`` and firm open orders from
``Extract_En_cours.xlsx``. Synthetic cover and synthetic in-transit quantities
are useful for what-if tests, but they should not be the default baseline.
"""

from __future__ import annotations

from collections.abc import Iterable


ERP_SNAPSHOT_INITIAL_STATE_ARGS: tuple[str, ...] = (
    "--initial-state-scale",
    "1",
    "--initial-factory-input-on-hand-days",
    "0",
    "--initial-supplier-output-on-hand-days",
    "0",
    "--initial-distribution-center-on-hand-days",
    "0",
    "--initial-customer-on-hand-days",
    "0",
    "--no-initial-seed-safety-time-on-hand",
    "--no-initial-seed-estimated-source-on-hand",
    "--no-initial-seed-in-transit",
    "--no-initial-seed-estimated-source-pipeline",
    "--mrp-base-stock-floor-factor",
    "0",
)


_INITIAL_STATE_FLAGS = {
    "--initial-state-scale",
    "--initial-factory-input-on-hand-days",
    "--initial-supplier-output-on-hand-days",
    "--initial-distribution-center-on-hand-days",
    "--initial-customer-on-hand-days",
    "--initial-seed-safety-time-on-hand",
    "--no-initial-seed-safety-time-on-hand",
    "--initial-seed-estimated-source-on-hand",
    "--no-initial-seed-estimated-source-on-hand",
    "--initial-in-transit-fill-ratio",
    "--initial-seed-in-transit",
    "--no-initial-seed-in-transit",
    "--initial-seed-estimated-source-pipeline",
    "--no-initial-seed-estimated-source-pipeline",
}


def living_supply_initial_state_args() -> list[str]:
    """Return simulator CLI args for the default observed ERP/MRP startup."""

    return list(ERP_SNAPSHOT_INITIAL_STATE_ARGS)


def has_explicit_initial_state_args(args: Iterable[str] | None) -> bool:
    """Whether a command already carries an explicit startup-state choice."""

    if not args:
        return False
    return any(str(arg) in _INITIAL_STATE_FLAGS for arg in args)


def merge_living_initial_state_args(args: Iterable[str] | None = None, *, enabled: bool = True) -> list[str]:
    """Prepend living-supply defaults unless the caller already specified them."""

    existing = [str(arg) for arg in (args or [])]
    if not enabled or has_explicit_initial_state_args(existing):
        return existing
    return [*living_supply_initial_state_args(), *existing]
