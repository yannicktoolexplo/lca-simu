# GEO link integrity audit

- Source JSON: `analysis/output8_GEO_normalized_final_business_reviewed.json`
- Detail CSV: `analysis/output8_GEO_business_reviewed_link_integrity_audit.csv`

## Summary

The previous map drew only strict adjacent links: `T4->T3`, `T3->T2`, `T2->T1`, `T1->OEM`.
Several supply records are valid but have an absent intermediate tier, so they looked visually disconnected from the constructor.
The map generator now adds dotted grey bridge links for these cases, without creating fake suppliers.

## Primary Links

- Records audited: 173
- Complete T4->T3->T2->T1->OEM records: 90
- Records needing a dotted bridge: 53
- Records missing T1: 11
- Records missing OEM: 0
- Status counts: continuous_direct=120, continuous_with_gap_bridge=53
- Missing-role counts: T2=46, T4=34, T1=11, T3=6

## All Links

- Records audited: 173
- Complete T4->T3->T2->T1->OEM records: 90
- Records needing a dotted bridge: 53
- Records missing T1: 11
- Records missing OEM: 0
- Status counts: continuous_direct=120, continuous_with_gap_bridge=53
- Missing-role counts: T2=46, T4=34, T1=11, T3=6

## Primary Examples Needing Bridge

- R1 `Ens. Equipements latéraux` / `A5086 - Aluminium`: T3->T1 missing:T2
- R2 `Ens. Stowage latéral` / `15CDV6 (chrome, molibdene, vanadium)`: T3->T1 missing:T2
- R5 `Bumper version porte` / `alliage Cu`: T3->T1 missing:T2
- R13 `Accoudoir allée` / `30NCD6 (nickel-chrome- molibdene)`: T3->T1 missing:T2
- R14 `Ens. Palette optimisée` / `35NC6 (nickel-chrome)`: T3->T1 missing:T2
- R29 `Accoudoir allée` / `A5086 - Aluminium`: T3->T1 missing:T2
- R30 `Bumper version porte` / `A5086 - Aluminium`: T3->T1 missing:T2
- R31 `Ens. Stowage latéral` / `A5086 - Aluminium`: T3->T1 missing:T2
- R33 `Ens. Structure fauteuil` / `4140 (acier)`: T3->T1 missing:T2
- R34 `Habillage sous fauteuil` / `A5086 - Aluminium`: T3->T1 missing:T2
- R35 `Manchette acc. Mobile` / `A5086 - Aluminium`: T3->T1 missing:T2
- R36 `Manchette équipée` / `A5086 - Aluminium`: T3->T1 missing:T2
- R37 `Renfort tubulaire` / `A5086 - Aluminium`: T3->T1 missing:T2
- R38 `Stowage assemblé avec porte` / `A5086 - Aluminium`: T3->T1 missing:T2
- R39 `Structure ottoman horizontale` / `A5086 - Aluminium`: T3->T1 missing:T2
- R40 `Support écran` / `A5086 - Aluminium`: T3->T1 missing:T2
- R41 `Support équipé` / `A5086 - Aluminium`: T3->T1 missing:T2
- R42 `Support manchette équipée` / `A5086 - Aluminium`: T3->T1 missing:T2
- R43 `Support NFC` / `A5086 - Aluminium`: T3->T1 missing:T2
- R44 `Renfort tubulaire` / `A6060 - Aluminium`: T3->T1 missing:T2

## Interpretation

- `continuous_direct`: direct adjacent links already connect the visible chain.
- `continuous_with_gap_bridge`: the chain reaches OEM only if the map bridges one or more absent intermediate tiers.
- `broken_no_oem` and `broken_no_supply_tier` would be hard errors; none should remain for the final JSON.
