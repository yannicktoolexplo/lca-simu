# GEO link integrity audit

- Source JSON: `analysis/output8_GEO_normalized_final_primary_complete.json`
- Detail CSV: `analysis/output8_GEO_primary_complete_link_integrity_audit.csv`

## Summary

The previous map drew only strict adjacent links: `T4->T3`, `T3->T2`, `T2->T1`, `T1->OEM`.
Several supply records are valid but have an absent intermediate tier, so they looked visually disconnected from the constructor.
The map generator now adds dotted grey bridge links for these cases, without creating fake suppliers.

## Primary Links

- Records audited: 173
- Complete T4->T3->T2->T1->OEM records: 173
- Records needing a dotted bridge: 0
- Records missing T1: 0
- Records missing OEM: 0
- Status counts: continuous_direct=173
- Missing-role counts: 

## All Links

- Records audited: 173
- Complete T4->T3->T2->T1->OEM records: 173
- Records needing a dotted bridge: 0
- Records missing T1: 0
- Records missing OEM: 0
- Status counts: continuous_direct=173
- Missing-role counts: 

## Primary Examples Needing Bridge


## Interpretation

- `continuous_direct`: direct adjacent links already connect the visible chain.
- `continuous_with_gap_bridge`: the chain reaches OEM only if the map bridges one or more absent intermediate tiers.
- `broken_no_oem` and `broken_no_supply_tier` would be hard errors; none should remain for the final JSON.
