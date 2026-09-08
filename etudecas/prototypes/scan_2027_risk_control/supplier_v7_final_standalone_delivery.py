#!/usr/bin/env python3
"""Render the qualified V7-authorized campaign as standalone HTML.

The mature three-view renderer is reused byte-for-byte.  This adapter changes
only the V7 identity/provenance.  It starts no simulation and never mutates an
older delivery.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_final_standalone_delivery as implementation_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)


implementation_v5 = implementation_v6.implementation_v5
delivery_v4 = implementation_v6.delivery_v4
SCHEMA_VERSION = "etudecas.supplier_v7_final_standalone_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
EXPECTED_V6_IMPLEMENTATION_SHA256 = (
    "3b52c8b85d9eff7f8e15a6b256276ca05da0144b2d1b53fa9ae7850d7b8c74dd"
)
V7FinalDeliveryError = implementation_v6.V6FinalDeliveryError

_V6_TITLE = "RESILIENCE-SCAN V6"
_V7_TITLE = "RESILIENCE-SCAN V7"
_V6_OVERLINE = "RÉSULTATS V6"
_V7_OVERLINE = "RÉSULTATS V7"
if (
    implementation_v6.HTML_TEMPLATE.count(_V6_TITLE) != 1
    or implementation_v6.HTML_TEMPLATE.count(_V6_OVERLINE) != 1
):
    raise RuntimeError("Unexpected V6 HTML branding template")
HTML_TEMPLATE = implementation_v6.HTML_TEMPLATE.replace(_V6_TITLE, _V7_TITLE).replace(
    _V6_OVERLINE, _V7_OVERLINE
)


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v6.__file__).resolve()
    digest = implementation_v5._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V6_IMPLEMENTATION_SHA256:
        raise V7FinalDeliveryError(f"Frozen V6 delivery adapter changed: {digest}")
    implementation_v6.validate_frozen_implementation()
    dashboard_v7.validate_frozen_implementation()
    return path


@contextmanager
def _v7_binding() -> Iterator[None]:
    validate_frozen_implementation()
    names: dict[str, Any] = {
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "MANIFEST_SCHEMA_VERSION": MANIFEST_SCHEMA_VERSION,
        "HTML_TEMPLATE": HTML_TEMPLATE,
        "__file__": str(Path(__file__).resolve()),
    }
    previous = {name: getattr(implementation_v5, name) for name in names}
    previous_dashboard = delivery_v4.campaign_dashboard
    try:
        for name, value in names.items():
            setattr(implementation_v5, name, value)
        delivery_v4.campaign_dashboard = dashboard_v7
        yield
    finally:
        delivery_v4.campaign_dashboard = previous_dashboard
        for name, value in previous.items():
            setattr(implementation_v5, name, value)


def build_delivery_payload(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v7_binding():
        return implementation_v5.build_delivery_payload(**kwargs)


def render_html(payload: Mapping[str, Any]) -> str:
    with _v7_binding():
        document = implementation_v5.render_html(payload)
    visible = re.sub(
        r'<script id="delivery-data".*?</script>', "", document, flags=re.DOTALL
    )
    if _V6_TITLE in visible or _V6_OVERLINE in visible:
        raise V7FinalDeliveryError("Visible V6 branding remains in V7 delivery")
    if _V7_TITLE not in visible or _V7_OVERLINE not in visible:
        raise V7FinalDeliveryError("Visible V7 branding is incomplete")
    return document


def manifest_path_for(output_html: Path) -> Path:
    return implementation_v5.manifest_path_for(output_html)


def build_delivery(**kwargs: Any) -> dict[str, Any]:
    with _v7_binding():
        manifest = implementation_v5.build_delivery(**kwargs)
    validate_delivery(Path(kwargs["output_html"]).resolve())
    return manifest


def validate_delivery(path: Path) -> dict[str, Any]:
    output = path.resolve()
    with _v7_binding():
        result = implementation_v5.validate_delivery(output)
    manifest = delivery_v4.read_json(manifest_path_for(output))
    generator = Path(__file__).resolve()
    visible = re.sub(
        r'<script id="delivery-data".*?</script>',
        "",
        output.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or Path(str(manifest.get("generator") or "")).resolve() != generator
        or manifest.get("generator_sha256") != implementation_v5._sha256_file(generator)  # noqa: SLF001
        or _V6_TITLE in visible
        or _V6_OVERLINE in visible
        or _V7_TITLE not in visible
        or _V7_OVERLINE not in visible
    ):
        raise V7FinalDeliveryError("V7 HTML identity or provenance changed")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = implementation_v5.parse_args(argv)
    try:
        if args.command == "build":
            result = build_delivery(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                curves_dir=args.curves_dir,
                replay_root=args.lot_replay_root,
                qualification_dir=args.qualification_dir,
                output_html=args.output_html,
                target_registry_path=args.target_registry,
                dashboard_html=args.dashboard_html,
                action_results_root=args.action_results_root,
                legacy_risk_html=args.legacy_risk_html,
                legacy_control_html=args.legacy_control_html,
            )
        else:
            result = validate_delivery(args.path)
    except (V7FinalDeliveryError, FileExistsError) as exc:
        print(f"LIVRAISON V7 REFUSÉE : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
