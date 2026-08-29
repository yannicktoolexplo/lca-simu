from __future__ import annotations

from decimal import Decimal

from .models import (
    Confidence,
    ConsolidationMode,
    ItemLotPolicy,
    LotPolicyRegistry,
    PolicyScope,
    PolicySource,
    ProcurementLotPolicy,
    ProductionLotPolicy,
    Quantity,
    QuantityGranularityPolicy,
    SourceKind,
    TransportConsolidationPolicy,
    UomPolicy,
)


INDUSTRIAL_LOT_SOURCE = PolicySource(
    reference="etudecas/data/source/Extract_Données_Complémentaires.xlsx:Taille de Lots",
    kind=SourceKind.INDUSTRIAL_SOURCE,
    confidence=Confidence.CONFIRMED,
    note="Industrial fixed/minimum/maximum lot-size extract.",
)

FIA_268967_SOURCE = PolicySource(
    reference="etudecas/data/source/268967.xlsx:FIA:item=708073",
    kind=SourceKind.INDUSTRIAL_SOURCE,
    confidence=Confidence.CONFIRMED,
    note="The source row states 5,000 KG. It must not be converted to 5,000,000 while retaining KG.",
)

INTERNAL_PFI_TRANSFER_SOURCE = PolicySource(
    reference="business_rule:773474_internal_weekly_transfer",
    kind=SourceKind.DERIVED,
    confidence=Confidence.HIGH,
    note=(
        "Internal PFI transfer is consolidated weekly. Dispatch granularity inherits "
        "the confirmed 3,200,000 G production lot; the FIA value 1 G is not a "
        "physical shipment lot."
    ),
)


def _canonical_policies() -> tuple[ItemLotPolicy, ...]:
    production_268091 = ProductionLotPolicy(
        item_id="item:268091",
        site_id="M-1810",
        uom="UN",
        minimum_qty=Decimal("14400"),
        maximum_qty=Decimal("142485"),
        multiple_qty=Decimal("14400"),
        source=INDUSTRIAL_LOT_SOURCE,
    )
    production_268967 = ProductionLotPolicy(
        item_id="item:268967",
        site_id="M-1430",
        uom="UN",
        fixed_qty=Decimal("107800"),
        minimum_qty=Decimal("107800"),
        maximum_qty=Decimal("107800"),
        multiple_qty=Decimal("107800"),
        source=INDUSTRIAL_LOT_SOURCE,
    )
    production_773474 = ProductionLotPolicy(
        item_id="item:773474",
        site_id="SDC-1450",
        uom="G",
        fixed_qty=Decimal("3200000"),
        multiple_qty=Decimal("3200000"),
        source=INDUSTRIAL_LOT_SOURCE,
    )
    procurement_708073 = ProcurementLotPolicy(
        item_id="item:708073",
        supplier_id="SDC-VD0520115A",
        destination_id="M-1430",
        uom="KG",
        moq=Decimal("5000"),
        order_multiple=Decimal("5000"),
        source=FIA_268967_SOURCE,
    )
    transport_773474 = TransportConsolidationPolicy(
        item_id="item:773474",
        origin_id="SDC-1450",
        destination_id="M-1430",
        uom="G",
        mode=ConsolidationMode.PERIODIC,
        window_days=7,
        minimum_dispatch_qty=Decimal("3200000"),
        dispatch_multiple=Decimal("3200000"),
        source=INTERNAL_PFI_TRANSFER_SOURCE,
    )
    return (
        ItemLotPolicy(
            item_id="item:268091",
            uom=UomPolicy(
                base_uom="UN",
                allowed_uoms=("UN",),
                production_uom="UN",
            ),
            production=(production_268091,),
            granularity=(
                QuantityGranularityPolicy(
                    item_id="item:268091",
                    scope=PolicyScope.PRODUCTION,
                    quantity=Quantity("14400", "UN"),
                    source=INDUSTRIAL_LOT_SOURCE,
                    site_id="M-1810",
                ),
            ),
        ),
        ItemLotPolicy(
            item_id="item:268967",
            uom=UomPolicy(
                base_uom="UN",
                allowed_uoms=("UN",),
                production_uom="UN",
            ),
            production=(production_268967,),
            granularity=(
                QuantityGranularityPolicy(
                    item_id="item:268967",
                    scope=PolicyScope.PRODUCTION,
                    quantity=Quantity("107800", "UN"),
                    source=INDUSTRIAL_LOT_SOURCE,
                    site_id="M-1430",
                ),
            ),
        ),
        ItemLotPolicy(
            item_id="item:708073",
            uom=UomPolicy(
                base_uom="G",
                allowed_uoms=("G", "KG"),
                procurement_uom="KG",
                transport_uom="KG",
            ),
            procurement=(procurement_708073,),
            granularity=(
                QuantityGranularityPolicy(
                    item_id="item:708073",
                    scope=PolicyScope.PROCUREMENT,
                    quantity=Quantity("5000", "KG"),
                    source=FIA_268967_SOURCE,
                    origin_id="SDC-VD0520115A",
                    destination_id="M-1430",
                ),
            ),
        ),
        ItemLotPolicy(
            item_id="item:773474",
            uom=UomPolicy(
                base_uom="G",
                allowed_uoms=("G", "KG"),
                production_uom="G",
                transport_uom="G",
            ),
            production=(production_773474,),
            granularity=(
                QuantityGranularityPolicy(
                    item_id="item:773474",
                    scope=PolicyScope.PRODUCTION,
                    quantity=Quantity("3200000", "G"),
                    source=INDUSTRIAL_LOT_SOURCE,
                    site_id="SDC-1450",
                ),
                QuantityGranularityPolicy(
                    item_id="item:773474",
                    scope=PolicyScope.TRANSPORT,
                    quantity=Quantity("3200000", "G"),
                    source=INTERNAL_PFI_TRANSFER_SOURCE,
                    origin_id="SDC-1450",
                    destination_id="M-1430",
                ),
            ),
            transport=(transport_773474,),
        ),
    )


def canonical_lot_policy_registry() -> LotPolicyRegistry:
    """Return a fresh registry so callers cannot mutate shared process state."""

    return LotPolicyRegistry.from_policies(_canonical_policies())
