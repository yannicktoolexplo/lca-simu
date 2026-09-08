#!/usr/bin/env python3
"""Run the additive V8 lot/cascade/action/curve delivery stage.

The mature V7 orchestration helpers are reused only while an explicit V8
compatibility context is active.  The public wrapper requires the native V8
upstream receipt, keeps all outputs separate, and never rewrites V4/V7 files.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_pipeline as implementation,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as common,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage2_pipeline.v1"
CONTRACT_NAME = implementation.CONTRACT_NAME
INVENTORY_NAME = implementation.INVENTORY_NAME
STATUS_NAME = implementation.STATUS_NAME
UPSTREAM_NAME = common.STAGE1_RECEIPT_NAME
Stage2PipelineError = implementation.Stage2PipelineError
_ORIGINAL_CONTRACT_PAYLOAD = implementation._contract_payload  # noqa: SLF001


def _contract_payload_v8(
    paths: common.Stage2Paths, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    """Strengthen the mature contract with the native V8 exposure proof."""

    base = _ORIGINAL_CONTRACT_PAYLOAD(paths, inventory)
    unsigned = {
        key: value for key, value in base.items() if key != "contract_signature"
    }
    scientific = dict(unsigned.get("scientific_contract") or {})
    scientific.update(
        {
            "stage1_required_status": (
                "accepted_v7_450_plus_v8_complete_3330_and_30_of_30_exposure"
            ),
            "v8_result_overlay_required": True,
            "target_exposure_gate": "18_lanes_each_comparable_on_30_of_30_seeds",
            "target_window_shared_across_three_states_and_30_seeds": True,
            "target_selection_uses_incident_outcomes": False,
            "target_selection_engine_runs": 0,
        }
    )
    unsigned["scientific_contract"] = scientific
    return common.signed(unsigned, "contract_signature")


def _delivery_v8(paths: common.Stage2Paths) -> dict[str, Any]:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_delivery as delivery_v8,
    )

    return delivery_v8.build_delivery(paths)


@contextmanager
def patched_v8_pipeline_context() -> Iterator[None]:
    """Temporarily give the mature helpers the V8 contracts and delivery."""

    previous_common = implementation.common
    previous_curves = implementation.curves_v7
    previous_schema = implementation.SCHEMA_VERSION
    previous_upstream = implementation.UPSTREAM_NAME
    previous_delivery = implementation._delivery  # noqa: SLF001
    previous_contract_payload = implementation._contract_payload  # noqa: SLF001
    implementation.common = common
    implementation.curves_v7 = curves_v7
    implementation.SCHEMA_VERSION = SCHEMA_VERSION
    implementation.UPSTREAM_NAME = UPSTREAM_NAME
    implementation._delivery = _delivery_v8  # noqa: SLF001
    implementation._contract_payload = _contract_payload_v8  # noqa: SLF001
    try:
        yield
    finally:
        implementation.common = previous_common
        implementation.curves_v7 = previous_curves
        implementation.SCHEMA_VERSION = previous_schema
        implementation.UPSTREAM_NAME = previous_upstream
        implementation._delivery = previous_delivery  # noqa: SLF001
        implementation._contract_payload = previous_contract_payload  # noqa: SLF001


def prepare_supervision(paths: common.Stage2Paths) -> dict[str, Any]:
    with patched_v8_pipeline_context():
        return implementation.prepare_supervision(paths)


def validate_bound_contract(
    paths: common.Stage2Paths,
    *,
    expected_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    with patched_v8_pipeline_context():
        return implementation.validate_bound_contract(
            paths, expected_contract=expected_contract
        )


def _verify_status(path: Path, contract_signature: str) -> dict[str, Any]:
    with patched_v8_pipeline_context():
        return implementation._verify_status(path, contract_signature)  # noqa: SLF001


def _selection(results_dir: Path) -> list[dict[str, Any]]:
    with patched_v8_pipeline_context():
        return implementation._selection(results_dir)  # noqa: SLF001


class Stage2Pipeline:
    """V8-bound façade around the resumable mature pipeline state machine."""

    def __init__(self, paths: common.Stage2Paths):
        self.paths = paths.resolved()
        with patched_v8_pipeline_context():
            self._inner = implementation.Stage2Pipeline(self.paths)

    @property
    def contract(self) -> dict[str, Any]:
        return self._inner.contract

    @property
    def inventory(self) -> dict[str, Any]:
        return self._inner.inventory

    @property
    def status_path(self) -> Path:
        return self._inner.status_path

    @property
    def status(self) -> dict[str, Any]:
        return self._inner.status

    def update(self, status: str, step: str, message_fr: str, **extra: Any) -> None:
        with patched_v8_pipeline_context():
            self._inner.update(status, step, message_fr, **extra)

    def guard(self) -> None:
        with patched_v8_pipeline_context():
            self._inner.guard()

    def execute(self) -> int:
        """Execute only after the immutable V8 upstream receipt can be rebuilt."""

        with patched_v8_pipeline_context():
            self._inner.guard()
            if common.probe_stage1(self.paths) != "accepted_stage1_complete":
                raise common.Stage2NotReady("L'étape 1 V8 n'est pas encore complète")
            upstream = common.validate_complete_stage1(self.paths)
            common.publish_new_or_identical(
                self.paths.supervision_dir / UPSTREAM_NAME,
                (
                    json.dumps(upstream, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                ).encode("utf-8"),
            )
            self._inner.guard()
            self._inner.update(
                "running",
                "validation_etape_1_v8",
                (
                    "Validation scientifique V7 (450 cas), registre d'exposition "
                    "V8 30/30 et matrice de campagne (90 références + 3 240 "
                    "incidents) revalidés."
                ),
                upstream_validation_signature=upstream["validation_signature"],
            )
            selection = implementation._selection(self.paths.results_dir)  # noqa: SLF001

            self._inner.guard()
            self._inner.update(
                "running",
                "courbes",
                "Construction des courbes nominales signées MM28 / MM7.",
            )
            curve_result = curves_v7.build_curve_package(
                self.paths.v7_plan_dir,
                self.paths.v7_run_dir,
                self.paths.curves_dir,
            )

            self._inner.guard()
            self._inner.update(
                "running",
                "lots",
                "Rejeux détaillés sans incident + incident, au plus trois dossiers.",
            )
            with common.v8_consumer_bindings():
                lot_result = implementation._run_lot_replays(  # noqa: SLF001
                    self.paths, selection
                )

            self._inner.guard()
            self._inner.update(
                "running",
                "qualification",
                "Qualification de la propagation physique réellement tracée.",
            )
            with common.v8_consumer_bindings():
                qualification = implementation._qualify(  # noqa: SLF001
                    self.paths, selection
                )

            self._inner.guard()
            self._inner.update(
                "running",
                "actions",
                "Test des seuls leviers représentables, décidés en boucle ouverte.",
            )
            with common.v8_consumer_bindings():
                action_result = implementation._run_actions(  # noqa: SLF001
                    self.paths, selection
                )

            self._inner.guard()
            self._inner.update(
                "running",
                "registre",
                "Consolidation des 3 240 incidents et des lots réellement disponibles.",
            )
            with common.v8_consumer_bindings():
                registry = implementation._registry(self.paths, selection)  # noqa: SLF001

            self._inner.guard()
            self._inner.update(
                "running",
                "html",
                "Construction du parcours autonome en français, trois vues maximum.",
            )
            delivery = _delivery_v8(self.paths)
            self._inner.guard()
            self._inner.update(
                "complete",
                "termine",
                "Étape 2 V8 terminée et revalidée.",
                results={
                    "curves": curve_result,
                    "lots": lot_result,
                    "qualification": qualification,
                    "actions": action_result,
                    "registry": registry,
                    "delivery": delivery,
                },
            )
            return 0


def add_path_arguments(parser: argparse.ArgumentParser) -> None:
    # The V7-named plan/run options intentionally identify the accepted V7
    # scientific source reused by V8; renaming them would hide that provenance.
    with patched_v8_pipeline_context():
        implementation.add_path_arguments(parser)


def paths_from_args(args: argparse.Namespace) -> common.Stage2Paths:
    with patched_v8_pipeline_context():
        return implementation.paths_from_args(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_path_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = paths_from_args(args)
    relay: Stage2Pipeline | None = None
    try:
        prepare_supervision(paths)
        with common.exclusive_lock(paths.supervision_dir / ".stage2.lock"):
            relay = Stage2Pipeline(paths)
            return relay.execute()
    except common.Stage2ScientificNoGo as exc:
        if relay is not None:
            relay.update("scientific_no_go", "arret", str(exc))
        print(f"ÉTAPE 2 V8 — ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except common.Stage2NotReady as exc:
        if relay is not None:
            relay.update("waiting", "attente_etape_1_v8", str(exc))
        print(f"ÉTAPE 2 V8 EN ATTENTE : {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        if relay is not None:
            relay.update(
                "interrupted_resumable",
                "interrompu",
                "Reprise V8 possible avec le même contrat.",
            )
        return 130
    except Exception as exc:
        if relay is not None:
            relay.update(
                "failed_resumable",
                "echec",
                str(exc),
                error={"type": type(exc).__name__, "message": str(exc)},
            )
        print(f"ÉTAPE 2 V8 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
