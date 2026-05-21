# Most probable missing-tier resolutions

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Input proposal CSV: `C:/dev/lca-simu/analysis/output8_GEO_missing_tier_proposals.csv`
- Output CSV: `C:/dev/lca-simu/analysis/output8_GEO_missing_tier_most_probable.csv`
- ChatGPT prompt: `C:/dev/lca-simu/analysis/output8_GEO_missing_tier_chatgpt_prompt.md`

## Summary

- Missing-tier rows: 94
- By tier: T2=47, T4=31, T1=11, T3=5
- By confidence: medium_high=43, medium=26, low=15, medium_low=10
- By resolution class: probable_internalized_process=43, probable_material_family_source=21, probable_direct_supplier_requires_part_number=9, manual_review_required=8, do_not_infer_from_cots=5, probable_existing_material_processor=3, probable_process_unknown_owner=3, probable_material_certificate_source=2

## Rule

- If a metal line misses T2, the most probable resolution is usually an internalized T2 process at the primary T1, not an invented external supplier.
- If a material line misses T4, the most probable resolution is a material-certificate source, not a named supplier unless the grade/site is known.
- If an electronics/COTS line misses upstream tiers, do not infer from brand names; require exact BOM/part-number data.
- Keep all rows non-active until business validation promotes them.

## Highest Confidence Rows

- R1 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R2 `15CDV6 (chrome, molibdene, vanadium)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (MGA Villeneuve St Lot).
- R5 `alliage Cu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R13 `30NCD6 (nickel-chrome- molibdene)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R14 `35NC6 (nickel-chrome)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R16 `35NC6 (nickel-chrome)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ETS Gattefin).
- R29 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R30 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R31 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R33 `4140 (acier)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R34 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R35 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R36 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R37 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R38 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R39 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R40 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R41 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R42 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R43 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R44 `A6060 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Groupe Segnere / SEGNERE Ade).
- R50 `de: aluminium cast part machining + tth compris dans le steel tinplated` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R51 `35NC6 (nickel-chrome)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R66 `Alu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R67 `Alu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R68 `Alu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R69 `A5086 - Aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (ESPACE).
- R70 `Alu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R81 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R94 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R95 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R96 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R98 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R99 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R100 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R101 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R102 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R116 `35NC6 (nickel-chrome)` T2: T2 le plus probable: operation internalisee chez le T1 primaire (MGA Villeneuve St Lot).
- R123 `Alu` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R138 `inox` T2: T2 le plus probable: operation internalisee chez le T1 primaire (Senior Aerospace Thailand).
- R154 `de: aluminium cast part machining glo: steel sheet stamping and bending` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R155 `de: aluminium cast part machining glo: steel sheet stamping and bending` T2: T2 le plus probable: operation internalisee chez le T1 primaire (SUMPAR).
- R161 `65% aluminium` T2: T2 le plus probable: operation internalisee chez le T1 primaire (JAMCO Aircraft Interiors - Niigata).