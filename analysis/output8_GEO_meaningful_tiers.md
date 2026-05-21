# Meaningful tiers for the aeronautical-seat supply network

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Taxonomy CSV: `C:/dev/lca-simu/analysis/output8_GEO_meaningful_tier_taxonomy.csv`
- Supplier assignment CSV: `C:/dev/lca-simu/analysis/output8_GEO_meaningful_supplier_tiers.csv`

## Tier taxonomy to keep

- **T4 / tier4_raw_material**: Raw material / primary producer. Mine/refinery/smelter/steelmaker/chemical producer or upstream commodity group supplying base materials.
- **T3 / tier3_first_transformation**: First transformation / material processor. Rolling, extrusion, forging, stockist/cutting service, textile/fiber/polymer first transformation.
- **T2 / tier2_second_transformation**: Second transformation / component processor. Injection, machining subcontractor, electronics/material component processor, textile/plastic sub-component supplier.
- **T1 / tier1**: Direct supplier / module or subassembly integrator. Supplier directly feeding FRN-F1F796DB13C8E2/OEM with seat structures, interiors, upholstery, restraint, IFE or assembled modules.
- **OEM / oem**: OEM / internal final integrator. FRN-AA08AEDDCB94EB / internal final assembly or customer-facing integrator; keep separate from external suppliers.
- **LOG / logistics**: Logistics provider. Transport provider; should not be modeled as a manufacturing tier node unless the simulation needs carrier capacity.
- **PKG / packaging**: Packaging / consumables. Packaging is present in LCA BOM but should be a separate auxiliary flow, not mixed with seat material tiers.

## Counts

- Records analysed: 175
- Supplier/site/tier assignments: 123
- Confidence: high=88, medium=34, review=1
- Modeling actions: keep_as_supply_tier_node=118, move_to_transport_layer=4, model_as_sink_or_internal_factory=1

| Role | Unique supplier/site/tier | Record appearances | Primary appearances | Region split |
|---|---:|---:|---:|---|
| tier4_raw_material | 30 | 594 | 144 | Outside_Europe=21, Europe_non_FR=6, France=3 |
| tier3_first_transformation | 29 | 661 | 170 | France=15, Outside_Europe=7, Europe_non_FR=7 |
| tier2_second_transformation | 27 | 382 | 128 | France=10, Outside_Europe=9, Europe_non_FR=8 |
| tier1 | 32 | 1312 | 166 | France=18, Outside_Europe=11, Europe_non_FR=3 |
| oem | 1 | 175 | 175 | France=1 |
| logistics | 4 | 64 | 16 | France=2, Europe_non_FR=1, Outside_Europe=1 |

## Interpretation

- The meaningful manufacturing tiers are `T4`, `T3`, `T2`, and `T1`; `OEM` is the sink/internal factory, not an external supplier tier.
- `LOG` should be kept in the route/transport layer, not mixed with production suppliers.
- `PKG` is meaningful for LCA and operational packaging risk, but it should be an auxiliary flow unless the simulation explicitly tests packaging shortages.
- For supplier-switch simulations, use `T1-T4` as switchable supplier layers, keep `OEM` fixed, and apply logistics disruptions separately.

## Highest-exposure assignments to review first

- OEM `FRN-AA08AEDDCB94EB` (France): 532.204045056 kg record-level exposure, records=175, confidence=high
- T3 `FRN-8D94FBDCC3B3B5` (France): 427.635072889 kg record-level exposure, records=104, confidence=high
- T1 `FRN-19277B67029E73` (Japan): 418.446230116 kg record-level exposure, records=86, confidence=high
- T1 `FRN-B4E809AFDBFA0B` (Japan): 418.446230116 kg record-level exposure, records=86, confidence=high
- T1 `FRN-AA9FC43191C9DB` (Philippines): 418.446230116 kg record-level exposure, records=86, confidence=high
- T4 `FRN-5AA9E59DA0B02F` (India): 393.081141476 kg record-level exposure, records=88, confidence=high
- T3 `FRN-6EF3EF62BA6339` (France): 377.866866376 kg record-level exposure, records=47, confidence=high
- T4 `FRN-7A25E45203FCC9` (China): 376.535123376 kg record-level exposure, records=43, confidence=medium
- T4 `FRN-60C89B8D6563EA` (India): 376.535123376 kg record-level exposure, records=43, confidence=high
- T3 `FRN-D2C24A0C097FC3` (France): 375.825446776 kg record-level exposure, records=42, confidence=medium
- T1 `FRN-2EC56F8EB8EC02` (Lithuania): 328.171771056 kg record-level exposure, records=36, confidence=high
- T4 `FRN-42D16514C836F9` (Canada): 316.903461476 kg record-level exposure, records=11, confidence=medium
- T4 `FRN-174726BD5498A5` (Canada): 316.903461476 kg record-level exposure, records=11, confidence=medium
- T1 `FRN-98C883F706EF89` (Thailand): 310.836482 kg record-level exposure, records=76, confidence=high
- T1 `FRN-4F3EF5C6442315` (France): 255.14289426 kg record-level exposure, records=12, confidence=high
- T1 `FRN-BEA11B23A9388A` (France): 255.14289426 kg record-level exposure, records=12, confidence=medium
- T1 `FRN-72A8D622F0F88D` (France): 243.649045467 kg record-level exposure, records=52, confidence=high
- T2 `FRN-213AAC10F8FF68` (United Kingdom): 240.9452244 kg record-level exposure, records=22, confidence=high
- T3 `FRN-0F56088BEA4986` (Japan): 125.24491928 kg record-level exposure, records=61, confidence=high
- T2 `FRN-0B3DAD918C8F64` (United States): 122.51808398 kg record-level exposure, records=62, confidence=high

## Caveat

The mass exposure column is a record-level screening proxy. It can double-count if aggregate `Siege` rows and detailed material rows are analysed together.
