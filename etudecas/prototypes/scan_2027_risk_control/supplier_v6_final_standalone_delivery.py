#!/usr/bin/env python3
"""Render the qualified V6 campaign as a three-view standalone HTML.

The mature V5 presentation logic remains byte-pinned.  This adapter changes
only the versioned schema, visible heading and generator provenance; it starts
no simulation and never mutates a V5 artifact.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v5_final_standalone_delivery as implementation_v5,
)


SCHEMA_VERSION = "etudecas.supplier_v6_final_standalone_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
EXPECTED_V5_IMPLEMENTATION_SHA256 = (
    "19174dc30c28ddfd4143f573414cc76279d1d5b384022b3c2d62d8962fa903be"
)
V6FinalDeliveryError = implementation_v5.V5FinalDeliveryError
delivery_v4 = implementation_v5.delivery_v4

_V5_TITLE = "RESILIENCE-SCAN V5"
_V6_TITLE = "RESILIENCE-SCAN V6"
_V5_OVERLINE = "RÉSULTATS V5"
_V6_OVERLINE = "RÉSULTATS V6"
if (
    implementation_v5.HTML_TEMPLATE.count(_V5_TITLE) != 1
    or implementation_v5.HTML_TEMPLATE.count(_V5_OVERLINE) != 1
):
    raise RuntimeError("Unexpected V5 HTML branding template")
HTML_TEMPLATE = implementation_v5.HTML_TEMPLATE.replace(
    _V5_TITLE, _V6_TITLE
).replace(_V5_OVERLINE, _V6_OVERLINE)


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v5.__file__).resolve()
    if implementation_v5._sha256_file(path) != EXPECTED_V5_IMPLEMENTATION_SHA256:  # noqa: SLF001
        raise V6FinalDeliveryError("Frozen V5 delivery implementation changed")
    return path


@contextmanager
def _v6_binding() -> Iterator[None]:
    validate_frozen_implementation()
    names: dict[str, Any] = {
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "MANIFEST_SCHEMA_VERSION": MANIFEST_SCHEMA_VERSION,
        "HTML_TEMPLATE": HTML_TEMPLATE,
        "__file__": str(Path(__file__).resolve()),
    }
    previous = {name: getattr(implementation_v5, name) for name in names}
    try:
        for name, value in names.items():
            setattr(implementation_v5, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(implementation_v5, name, value)


def build_delivery_payload(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    with _v6_binding():
        return implementation_v5.build_delivery_payload(**kwargs)


def render_html(payload: Mapping[str, Any]) -> str:
    with _v6_binding():
        document = implementation_v5.render_html(payload)
    visible = re.sub(
        r'<script id="delivery-data".*?</script>', "", document, flags=re.DOTALL
    )
    if _V5_TITLE in visible or _V5_OVERLINE in visible:
        raise V6FinalDeliveryError("Visible V5 branding remains in the V6 delivery")
    if _V6_TITLE not in visible or _V6_OVERLINE not in visible:
        raise V6FinalDeliveryError("Visible V6 branding is incomplete")
    return document


def manifest_path_for(output_html: Path) -> Path:
    return implementation_v5.manifest_path_for(output_html)


def build_delivery(**kwargs: Any) -> dict[str, Any]:
    with _v6_binding():
        manifest = implementation_v5.build_delivery(**kwargs)
    output = Path(kwargs["output_html"]).resolve()
    validate_delivery(output)
    return manifest


def validate_delivery(path: Path) -> dict[str, Any]:
    output = path.resolve()
    with _v6_binding():
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
        or manifest.get("generator_sha256")
        != implementation_v5._sha256_file(generator)  # noqa: SLF001
        or _V5_TITLE in visible
        or _V5_OVERLINE in visible
        or _V6_TITLE not in visible
        or _V6_OVERLINE not in visible
    ):
        raise V6FinalDeliveryError("V6 HTML identity or generator provenance changed")
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
    except (V6FinalDeliveryError, FileExistsError) as exc:
        print(f"LIVRAISON V6 REFUSÉE : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
