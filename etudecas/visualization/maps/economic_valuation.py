"""Map contract for monetary scopes and incomplete valuation."""
from __future__ import annotations
from typing import Any


def economic_cost_view(summary: dict[str, Any]) -> dict[str, Any]:
    kpis = summary.get("kpis") or {}
    valuation = summary.get("economic_valuation") or {}
    complete = valuation.get("complete") is True and valuation.get("status") == "complete"
    status = "complete" if complete else ("incomplete" if valuation else "unknown")
    def amount(*keys: str) -> float | None:
        for key in keys:
            if kpis.get(key) is not None:
                return float(kpis[key])
        return None
    operating = amount("known_cost_subtotal", "total_cost")
    external = amount("total_external_procurement_cost", "exceptional_supply_cost")
    exposure = amount("known_economic_exposure_subtotal", "total_economic_exposure")
    if exposure is None and operating is not None and external is not None:
        exposure = operating + external
    return {
        "operating_cost": operating, "external_procurement_cost": external,
        "economic_exposure": exposure, "valuation_status": status,
        "valuation_complete": complete, "economic_ranking_eligible": complete,
        "cost_label": "Coût opérationnel simulé" if complete else "Coût partiellement valorisé — sous-total connu",
        "economic_valuation": valuation or {"status": "unknown", "complete": False, "metric_basis": "historical_valuation_unverified"},
        "cost_scope_note": "Opérationnel : possession, production, achats et transport opérationnels. Approvisionnement externe : complément séparé. Exposition économique : somme de ces deux périmètres ; ce sont des coûts du modèle.",
    }
