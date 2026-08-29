"""Additive post-feedback probes for closed-loop identification.

The ordinary control schedule and the state-feedback providers intentionally
remain mutually exclusive.  A control probe is a different, experimental
interface: it adds a small, precomputed offset to an already resolved V2/V3
feedback command immediately before the physical engine uses that command.

For an action with neutral value ``n`` the composition is::

    u_applied = clip(u_feedback + (u_probe - n), engineering_bounds)

The probe never observes engine state and therefore cannot weaken the
controller's J-to-J+1 causal contract.  Warm-up exclusion is owned by the
engine integration, which only resolves probes on measured days.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping

from .control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
    ControlCatalog,
    ControlNumber,
    ControlSchedule,
    ControlScheduleError,
    ControlScheduleRow,
    ResolvedAction,
    ResolvedControl,
    load_control_schedule,
)


CONTROL_PROBE_ACTIONS: tuple[str, ...] = (
    "order_multiplier",
    "safety_stock_multiplier",
    "production_target_multiplier",
)
CONTROL_PROBE_MODE = "post_feedback_additive"

CONTROL_PROBE_COMPOSITION_COLUMNS: tuple[str, ...] = (
    "day",
    "resolved_node_id",
    "resolved_supplier_id",
    "resolved_item_id",
    "resolved_dst_node_id",
    "action",
    "neutral_value",
    "feedback_requested",
    "feedback_effective",
    "probe_requested",
    "probe_effective",
    "probe_delta",
    "composed_unbounded",
    "composed_effective",
    "composition_bound",
    "composition_clipped",
    "feedback_policy",
    "feedback_source_line",
    "probe_policy",
    "probe_source_line",
    "probe_source_node_id",
    "probe_source_supplier_id",
    "probe_source_item_id",
    "probe_source_dst_node_id",
    "probe_scope_specificity",
    "composition_mode",
)


class ControlProbeError(ValueError):
    """Raised when a closed-loop probe is unsafe or ambiguous."""


@dataclass(frozen=True)
class ControlProbeSchedule:
    """A schedule restricted to the three supported identification levers."""

    schedule: ControlSchedule
    path: Path

    @property
    def enabled(self) -> bool:
        return self.schedule.enabled

    @property
    def rows(self) -> tuple[ControlScheduleRow, ...]:
        return self.schedule.rows

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.schedule.warnings

    def resolve(
        self,
        day: int,
        node_id: str = "",
        supplier_id: str = "",
        item_id: str = "",
        dst_node_id: str = "",
    ) -> ResolvedControl:
        return self.schedule.resolve(
            day,
            node_id=node_id,
            supplier_id=supplier_id,
            item_id=item_id,
            dst_node_id=dst_node_id,
        )


@dataclass(frozen=True)
class ComposedProbeAction:
    """One feedback action after addition of an independent probe offset."""

    name: str
    requested: ControlNumber
    effective: ControlNumber
    bound: str
    source_line: int | None
    policy: str
    node_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    specificity: int
    feedback_action: ResolvedAction
    probe_action: ResolvedAction
    neutral_value: ControlNumber
    probe_delta: float
    composed_unbounded: float

    @property
    def applied(self) -> bool:
        return self.feedback_action.applied or self.probe_action.applied

    @property
    def composition_clipped(self) -> bool:
        return self.bound != "none"

    def composition_metadata(self) -> dict[str, Any]:
        feedback = self.feedback_action
        probe = self.probe_action
        return {
            "control_probe_applied": int(probe.applied),
            "control_probe_mode": CONTROL_PROBE_MODE,
            "control_neutral_value": self.neutral_value,
            "control_feedback_requested": feedback.requested,
            "control_feedback_effective": feedback.effective,
            "control_probe_requested": probe.requested,
            "control_probe_effective": probe.effective,
            "control_probe_delta": self.probe_delta,
            "control_composed_unbounded": self.composed_unbounded,
            "control_composed_effective": self.effective,
            "control_composition_bound": self.bound,
            "control_composition_clipped": int(self.composition_clipped),
            "control_feedback_policy": feedback.policy,
            "control_feedback_source_line": (
                feedback.source_line if feedback.source_line is not None else ""
            ),
            "control_probe_policy": probe.policy,
            "control_probe_source_line": (
                probe.source_line if probe.source_line is not None else ""
            ),
            "control_probe_source_node_id": probe.node_id,
            "control_probe_source_supplier_id": probe.supplier_id,
            "control_probe_source_item_id": probe.item_id,
            "control_probe_source_dst_node_id": probe.dst_node_id,
            "control_probe_scope_specificity": probe.specificity,
        }


@dataclass(frozen=True)
class ProbeResolvedControl:
    """Duck-compatible :class:`ResolvedControl` carrying dual provenance."""

    day: int
    node_id: str = ""
    supplier_id: str = ""
    item_id: str = ""
    dst_node_id: str = ""
    order_multiplier: float = 1.0
    safety_stock_multiplier: float = 1.0
    production_target_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    external_procurement_multiplier: float = 1.0
    expedite_level: float = 0.0
    lead_time_adjustment_days: int = 0
    priority_weight: float = 1.0
    metadata: tuple[ResolvedAction | ComposedProbeAction, ...] = ()
    matched_source_lines: tuple[int, ...] = ()

    @property
    def enabled(self) -> bool:
        return any(action.applied for action in self.metadata)

    @property
    def policies(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                action.policy
                for action in self.metadata
                if action.applied and action.policy
            )
        )

    @property
    def policy(self) -> str:
        return "|".join(self.policies)

    @property
    def requested(self) -> dict[str, ControlNumber]:
        return {action.name: action.requested for action in self.metadata}

    @property
    def effective(self) -> dict[str, ControlNumber]:
        return {action.name: action.effective for action in self.metadata}

    @property
    def bound(self) -> dict[str, str]:
        return {action.name: action.bound for action in self.metadata}

    @property
    def source_lines(self) -> dict[str, int | None]:
        return {action.name: action.source_line for action in self.metadata}

    def action(self, name: str) -> ResolvedAction | ComposedProbeAction:
        try:
            return next(action for action in self.metadata if action.name == name)
        except StopIteration as exc:
            raise KeyError(name) from exc

    def composition_rows(self) -> list[dict[str, Any]]:
        """Return one row for each probe action resolved on this exact scope."""

        rows: list[dict[str, Any]] = []
        for action in self.metadata:
            if not isinstance(action, ComposedProbeAction):
                continue
            probe = action.probe_action
            feedback = action.feedback_action
            rows.append(
                {
                    "day": self.day,
                    "resolved_node_id": self.node_id,
                    "resolved_supplier_id": self.supplier_id,
                    "resolved_item_id": self.item_id,
                    "resolved_dst_node_id": self.dst_node_id,
                    "action": action.name,
                    "neutral_value": action.neutral_value,
                    "feedback_requested": feedback.requested,
                    "feedback_effective": feedback.effective,
                    "probe_requested": probe.requested,
                    "probe_effective": probe.effective,
                    "probe_delta": action.probe_delta,
                    "composed_unbounded": action.composed_unbounded,
                    "composed_effective": action.effective,
                    "composition_bound": action.bound,
                    "composition_clipped": int(action.composition_clipped),
                    "feedback_policy": feedback.policy,
                    "feedback_source_line": (
                        feedback.source_line
                        if feedback.source_line is not None
                        else ""
                    ),
                    "probe_policy": probe.policy,
                    "probe_source_line": (
                        probe.source_line if probe.source_line is not None else ""
                    ),
                    "probe_source_node_id": probe.node_id,
                    "probe_source_supplier_id": probe.supplier_id,
                    "probe_source_item_id": probe.item_id,
                    "probe_source_dst_node_id": probe.dst_node_id,
                    "probe_scope_specificity": probe.specificity,
                    "composition_mode": CONTROL_PROBE_MODE,
                }
            )
        return rows

    def to_ledger_rows(
        self,
        *,
        include_neutral: bool = False,
        status: str = "resolved",
        extra: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Serialize standard ledger fields plus probe-composition evidence."""

        rows: list[dict[str, Any]] = []
        for action in self.metadata:
            if not include_neutral and not action.applied:
                continue
            row: dict[str, Any] = {
                "day": self.day,
                "resolved_node_id": self.node_id,
                "resolved_supplier_id": self.supplier_id,
                "resolved_item_id": self.item_id,
                "resolved_dst_node_id": self.dst_node_id,
                "policy": action.policy,
                "action": action.name,
                "requested": action.requested,
                "effective": action.effective,
                "bound": action.bound,
                "status": status,
                "source_line": (
                    action.source_line if action.source_line is not None else ""
                ),
                "scope_type": "global" if action.specificity == 0 else "targeted",
                "scope_specificity": action.specificity,
                "source_node_id": action.node_id,
                "source_supplier_id": action.supplier_id,
                "source_item_id": action.item_id,
                "source_dst_node_id": action.dst_node_id,
                "matched_source_lines": ";".join(
                    str(line) for line in self.matched_source_lines
                ),
            }
            if isinstance(action, ComposedProbeAction):
                row.update(action.composition_metadata())
            if extra:
                row.update(extra)
            rows.append(row)
        return rows


def _same_number(left: ControlNumber, right: ControlNumber) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def load_control_probe_schedule(
    path: Path | str,
    *,
    catalog: ControlCatalog | None = None,
) -> ControlProbeSchedule:
    """Load a schedule and retain only supported, unclamped probe levers.

    Unsupported action columns may be present only at their exact neutral
    value.  They are discarded so they cannot be mistaken for applied probe
    actions in downstream ledgers.  Any non-neutral unsupported lever, bound
    clamp, or row without a supported action is rejected.
    """

    probe_path = Path(path).resolve()
    try:
        loaded = load_control_schedule(probe_path, catalog=catalog)
    except ControlScheduleError as exc:
        raise ControlProbeError(str(exc)) from exc

    sanitized_rows: list[ControlScheduleRow] = []
    for row in loaded.rows:
        requested: dict[str, ControlNumber] = {}
        effective: dict[str, ControlNumber] = {}
        bound: dict[str, str] = {}
        unsupported: list[str] = []
        for action_name, requested_value in row.requested.items():
            effective_value = row.effective[action_name]
            neutral = CONTROL_BOUNDS[action_name].neutral
            if action_name not in CONTROL_PROBE_ACTIONS:
                if not _same_number(requested_value, neutral) or not _same_number(
                    effective_value, neutral
                ):
                    unsupported.append(action_name)
                continue
            if row.bound[action_name] != "none":
                raise ControlProbeError(
                    f"Line {row.source_line}: probe action {action_name!r} "
                    "cannot rely on control-bound clamping."
                )
            requested[action_name] = requested_value
            effective[action_name] = effective_value
            bound[action_name] = row.bound[action_name]
        if unsupported:
            raise ControlProbeError(
                f"Line {row.source_line}: unsupported non-neutral probe actions: "
                + ", ".join(sorted(unsupported))
                + ". Allowed actions are: "
                + ", ".join(CONTROL_PROBE_ACTIONS)
                + "."
            )
        if not effective:
            raise ControlProbeError(
                f"Line {row.source_line}: every probe row must set at least one "
                "supported action."
            )
        sanitized_rows.append(
            ControlScheduleRow(
                day=row.day,
                policy=row.policy,
                node_id=row.node_id,
                supplier_id=row.supplier_id,
                item_id=row.item_id,
                dst_node_id=row.dst_node_id,
                requested=requested,
                effective=effective,
                bound=bound,
                source_line=row.source_line,
            )
        )
    if not sanitized_rows:
        raise ControlProbeError("Control probe schedule contains no action rows.")
    return ControlProbeSchedule(
        schedule=ControlSchedule(
            rows=tuple(sanitized_rows),
            warnings=tuple(loaded.warnings),
            path=probe_path,
        ),
        path=probe_path,
    )


def compose_feedback_with_probe(
    feedback: ResolvedControl,
    probe: ResolvedControl,
) -> ResolvedControl | ProbeResolvedControl:
    """Add one resolved probe to one resolved feedback command.

    If no probe row matches the exact resolution request, the original
    feedback object is returned by identity.  This keeps unaffected scopes on
    the historical execution path.
    """

    if feedback.day != probe.day or (
        feedback.node_id,
        feedback.supplier_id,
        feedback.item_id,
        feedback.dst_node_id,
    ) != (
        probe.node_id,
        probe.supplier_id,
        probe.item_id,
        probe.dst_node_id,
    ):
        raise ControlProbeError(
            "Feedback and probe resolutions must use the same day and exact scope."
        )
    if not probe.enabled:
        return feedback

    metadata: list[ResolvedAction | ComposedProbeAction] = []
    values: dict[str, ControlNumber] = {}
    for action_name in ACTION_FIELDS:
        feedback_action = feedback.action(action_name)
        probe_action = probe.action(action_name)
        if not probe_action.applied:
            metadata.append(feedback_action)
            values[action_name] = feedback_action.effective
            continue
        if action_name not in CONTROL_PROBE_ACTIONS:
            raise ControlProbeError(
                f"Unsupported resolved probe action {action_name!r}."
            )
        neutral = CONTROL_BOUNDS[action_name].neutral
        probe_delta = float(probe_action.effective) - float(neutral)
        unbounded = float(feedback_action.effective) + probe_delta
        composed, bound = CONTROL_BOUNDS[action_name].apply(unbounded)
        composed = float(composed)
        source_line = (
            feedback_action.source_line
            if feedback_action.source_line is not None
            else -int(probe_action.source_line or 1)
        )
        policies = tuple(
            dict.fromkeys(
                value
                for value in (feedback_action.policy, probe_action.policy)
                if value
            )
        )
        action = ComposedProbeAction(
            name=action_name,
            requested=unbounded,
            effective=composed,
            bound=bound,
            source_line=source_line,
            policy="|".join(policies),
            node_id=probe_action.node_id,
            supplier_id=probe_action.supplier_id,
            item_id=probe_action.item_id,
            dst_node_id=probe_action.dst_node_id,
            specificity=probe_action.specificity,
            feedback_action=feedback_action,
            probe_action=probe_action,
            neutral_value=neutral,
            probe_delta=probe_delta,
            composed_unbounded=unbounded,
        )
        metadata.append(action)
        values[action_name] = composed

    matched_lines = tuple(
        dict.fromkeys(
            (*feedback.matched_source_lines, *probe.matched_source_lines)
        )
    )
    return ProbeResolvedControl(
        day=feedback.day,
        node_id=feedback.node_id,
        supplier_id=feedback.supplier_id,
        item_id=feedback.item_id,
        dst_node_id=feedback.dst_node_id,
        order_multiplier=float(values["order_multiplier"]),
        safety_stock_multiplier=float(values["safety_stock_multiplier"]),
        production_target_multiplier=float(
            values["production_target_multiplier"]
        ),
        capacity_multiplier=float(values["capacity_multiplier"]),
        external_procurement_multiplier=float(
            values["external_procurement_multiplier"]
        ),
        expedite_level=float(values["expedite_level"]),
        lead_time_adjustment_days=int(values["lead_time_adjustment_days"]),
        priority_weight=float(values["priority_weight"]),
        metadata=tuple(metadata),
        matched_source_lines=matched_lines,
    )


__all__ = [
    "CONTROL_PROBE_ACTIONS",
    "CONTROL_PROBE_COMPOSITION_COLUMNS",
    "CONTROL_PROBE_MODE",
    "ComposedProbeAction",
    "ControlProbeError",
    "ControlProbeSchedule",
    "ProbeResolvedControl",
    "compose_feedback_with_probe",
    "load_control_probe_schedule",
]
