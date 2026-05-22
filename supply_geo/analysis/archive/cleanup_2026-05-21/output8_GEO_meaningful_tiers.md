# Meaningful tiers for the aeronautical-seat supply network

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Taxonomy CSV: `C:/dev/lca-simu/analysis/output8_GEO_meaningful_tier_taxonomy.csv`
- Supplier assignment CSV: `C:/dev/lca-simu/analysis/output8_GEO_meaningful_supplier_tiers.csv`

## Tier taxonomy to keep

- **T4 / tier4_raw_material**: Raw material / primary producer. Mine/refinery/smelter/steelmaker/chemical producer or upstream commodity group supplying base materials.
- **T3 / tier3_first_transformation**: First transformation / material processor. Rolling, extrusion, forging, stockist/cutting service, textile/fiber/polymer first transformation.
- **T2 / tier2_second_transformation**: Second transformation / component processor. Injection, machining subcontractor, electronics/material component processor, textile/plastic sub-component supplier.
- **T1 / tier1**: Direct supplier / module or subassembly integrator. Supplier directly feeding Safran/OEM with seat structures, interiors, upholstery, restraint, IFE or assembled modules.
- **OEM / oem**: OEM / internal final integrator. Safran Seats / internal final assembly or customer-facing integrator; keep separate from external suppliers.
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

- OEM `Safran Seats / Safran internal group` (France): 532.204045056 kg record-level exposure, records=175, confidence=high
- T3 `thyssenkrupp Materials France` (France): 427.635072889 kg record-level exposure, records=104, confidence=high
- T1 `JAMCO Aircraft Interiors - Miyazaki` (Japan): 418.446230116 kg record-level exposure, records=86, confidence=high
- T1 `JAMCO Aircraft Interiors - Niigata` (Japan): 418.446230116 kg record-level exposure, records=86, confidence=high
- T1 `JAMCO Philippines Inc.` (Philippines): 418.446230116 kg record-level exposure, records=86, confidence=high
- T4 `Tata Steel` (India): 393.081141476 kg record-level exposure, records=88, confidence=high
- T3 `Euralliage Ile de France` (France): 377.866866376 kg record-level exposure, records=47, confidence=high
- T4 `Aluminium Corporation of China / Chalco` (China): 376.535123376 kg record-level exposure, records=43, confidence=medium
- T4 `Hindalco Industries` (India): 376.535123376 kg record-level exposure, records=43, confidence=high
- T3 `Aluminium France` (France): 375.825446776 kg record-level exposure, records=42, confidence=medium
- T1 `J&C Aero` (Lithuania): 328.171771056 kg record-level exposure, records=36, confidence=high
- T4 `Rio Tinto Alma Works` (Canada): 316.903461476 kg record-level exposure, records=11, confidence=medium
- T4 `Rio Tinto Fer et Titane` (Canada): 316.903461476 kg record-level exposure, records=11, confidence=medium
- T1 `Senior Aerospace Thailand` (Thailand): 310.836482 kg record-level exposure, records=76, confidence=high
- T1 `Airbus Atlantic / STELIA Aerospace` (France): 255.14289426 kg record-level exposure, records=12, confidence=high
- T1 `COLLINS` (France): 255.14289426 kg record-level exposure, records=12, confidence=medium
- T1 `ACH` (France): 243.649045467 kg record-level exposure, records=52, confidence=high
- T2 `MGR Foamtex Ltd` (United Kingdom): 240.9452244 kg record-level exposure, records=22, confidence=high
- T3 `Toray Industries` (Japan): 125.24491928 kg record-level exposure, records=61, confidence=high
- T2 `DuPont de Nemours` (United States): 122.51808398 kg record-level exposure, records=62, confidence=high

## Caveat

The mass exposure column is a record-level screening proxy. It can double-count if aggregate `Siege` rows and detailed material rows are analysed together.
