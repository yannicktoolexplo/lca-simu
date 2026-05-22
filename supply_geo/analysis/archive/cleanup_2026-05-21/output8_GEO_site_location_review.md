# Site-grade location review - output8_GEO

- Input: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_business_reviewed.json`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_site_reviewed.json`
- Change log: `C:/dev/lca-simu/analysis/output8_GEO_site_location_review_changes.csv`
- Applied record-level changes: **524**
- Source-backed fix rules: **20**

## Corrections appliquees

| fix_id | site retenu | occurrences | confiance | source | action simulation |
|---|---:|---:|---|---|---|
| SITE_TATA_JAMSHEDPUR | FRN-5AA9E59DA0B02F Jamshedpur Works | 86 | medium_high | https://sources.invalid/FRN-5AA9E59DA0B02F/5592a987c0e8bf05 | Use Jamshedpur Works as steel mill candidate; keep certificate validation required. |
| SITE_DUPONT_SPRUANCE | DuPont Spruance Manufacturing Site | 61 | high | https://sources.invalid/FRN-0B3DAD918C8F64/ecd21ddc8101ccb0 | Replace Wilmington HQ fallback with Spruance manufacturing site for DuPont fiber/polymer exposure. |
| SITE_BAOSTEEL_BAOSHAN | Baosteel Baoshan / Fujin Road site | 44 | medium | https://sources.invalid/FRN-CF71418802439F/61e2b40f4124dc67 | Use Baoshan/Fujin Road as China steel mill candidate; require certificate for active allocation. |
| SITE_FRN-3C5607FC501E5A_INDUSTEEL | FRN-3C5607FC501E5A Industeel Le Creusot | 43 | medium | https://sources.invalid/FRN-3C5607FC501E5A/19f83839bed63ba0 | Use Industeel Le Creusot as special-steel scenario candidate; certificate required before hard allocation. |
| SITE_AUBERT_ANCIZES | FRN-83186B5AEF84D8 Les Ancizes | 43 | high | https://sources.invalid/FRN-83186B5AEF84D8/9b340f758cab879f | Replace Aubiere/Clermont fallback with Les Ancizes metallurgical site. |
| SITE_FRN-7A25E45203FCC9_QINGHAI | FRN-7A25E45203FCC9 Qinghai Branch / Beichuan Industrial Park | 42 | medium | https://sources.invalid/FRN-7A25E45203FCC9/8c2766000e43f27a | Replace Beijing fallback with Qinghai smelter candidate; keep allocation validation required. |
| SITE_FRN-191F6AC0669F77_RENUKOOT | FRN-191F6AC0669F77 Renukoot | 42 | high | https://sources.invalid/FRN-60C89B8D6563EA/861eab1c437f262c | Replace Mumbai corporate fallback with Renukoot aluminium plant. |
| SITE_NUCOR_BERKELEY | Nucor Steel Berkeley | 42 | medium_high | https://sources.invalid/FRN-B8E884308EA449/03613c032bda4791 | Replace Charlotte HQ fallback with Nucor Berkeley mill candidate. |
| SITE_FRN-34B2AC7037114C_WARRICK | FRN-34B2AC7037114C Warrick Operations | 34 | high | https://sources.invalid/FRN-34B2AC7037114C/a5c0942c79e534b3 | Replace Pittsburgh fallback with Warrick primary aluminium operation. |
| SITE_FRN-798BE9ED657B85_ISSOIRE | FRN-798BE9ED657B85 Issoire | 31 | high | https://sources.invalid/FRN-798BE9ED657B85/6f3c9703af462853 | Replace Voreppe R&D fallback with Issoire aerospace production site. |
| SITE_FRN-0CA3DB5897A052 | FRN-0CA3DB5897A052 Old Dye Works showroom / company site | 29 | medium | https://sources.invalid/FRN-0CA3DB5897A052/83f2b3b47ff32399 | Replace town centroid with company postcode-level site; validate mill/weaver before production allocation. |
| SITE_FRN-9C546CCC918C61_NAGOYA_NYLON | FRN-9C546CCC918C61 Nagoya Plant | 10 | high_for_nylon_only | https://sources.invalid/FRN-0F56088BEA4986/fbe4410125ad0498 | Use Nagoya for FRN-9C546CCC918C61 nylon records only; keep generic textile/composite FRN-9C546CCC918C61 records unchanged unless grade is known. |
| SITE_MITSUBISHI_TIELT_ERTALON | FRN-6378B78052F4FE Advanced Materials Tielt | 7 | high_for_ertalon_only | https://sources.invalid/FRN-6378B78052F4FE/7fe70d1186a82d79 | Use Tielt for Ertalon/MCAM records; keep non-Ertalon Mitsubishi records unchanged. |
| SITE_SHINETSU_GUNMA_ISOBE | Shin-Etsu Chemical Gunma Complex Isobe Plant | 2 | medium_high | https://sources.invalid/FRN-332F92E4BA4B00/fdebbb2c4398c29d | Replace Tokyo HQ/city fallback with Gunma silicone plant area. |
| SITE_FRN-BDE3FD68E4E87F_BLACKBURN | FRN-BDE3FD68E4E87F Blackburn | 2 | medium_high | https://sources.invalid/FRN-BDE3FD68E4E87F/30c348c801664ac6 | Replace Blackburn city point with Blakewater Road/Greenbank Business Park area. |
| SITE_FRN-9C546CCC918C61_EHIME_CARBON | FRN-9C546CCC918C61 Ehime Plant | 2 | medium_high | https://sources.invalid/FRN-8A956B599D7510/472a15487d9df296 | Use Ehime for carbon-fiber record; exact gate coordinate can be refined later. |
| SITE_DAIO_MISHIMA | FRN-B7600B824E7BC7 Mishima Mill | 1 | medium | https://sources.invalid/FRN-B7600B824E7BC7/5b8fa58f3adb9d79 | Replace generic Shikokuchuo city note with Mishima Mill site identity; improve coordinates if local geocoder available. |
| SITE_KEMCO_STLOUIS | Kemco/Mastercraft Building 1 | 1 | high | https://sources.invalid/FRN-EFD76ECB77D7DC/ccd5f84c2d347152 | Replace St. Louis city fallback with Kemco/Mastercraft building. |
| SITE_FRN-52D5AE23024E5C_LINDENBERG | FRN-42EDB7DB79E4B3 Lindenberg GmbH | 1 | high | https://sources.invalid/FRN-42EDB7DB79E4B3/c887764179525dd2 | Replace Lindenberg city fallback with the FRN-52D5AE23024E5C site address. |
| SITE_NORDIC_SAFFLE | FRN-AC50E317D82C5C Saffle Mill | 1 | high | https://sources.invalid/FRN-AC50E317D82C5C/2dd36d5ebf78c77c | Replace multi-mill fallback with Saffle mill for this paper/padding scenario. |

## Decisions non appliquees ou partielles

| fournisseur | decision | candidat | raison | action simulation |
|---|---|---|---|---|
| FRN-7BCA1282BFEC03 | not_applied | XPO Europe HQ, 192 Avenue Thiers, Lyon, France, or route-specific XPO operating center | FRN-B5DA4EA4F8BEF1 nodes should be modeled as route legs/hubs, not as a supplier plant. Public data does not identify the actual route hub for these records. | Keep as logistics provider; require route lane or hub assignment before replacing Greenwich/Lyon HQ. |
| FRN-B9C4C86C42C8B4 | not_applied | FRN-2B32314A8C4A0F, Defense & Marine, Middletown, PA candidate | TE has AD&M operations but the exact cable/bracket part number is missing; a plant assignment would be false precision. | Keep Berwyn/HQ candidate inactive for site simulation until PN/BOM/AVL is available. |
| FRN-6378B78052F4FE | partial_only | FRN-6378B78052F4FE Advanced Materials Tielt applied only for Ertalon records | Non-Ertalon Mitsubishi records include nylon, LCD/display and generic molded plastic; public data is insufficient to allocate all to Tielt. | Use Tielt only for Ertalon; require grade/PN for other Mitsubishi records. |
| FRN-0F56088BEA4986 | partial_only | Nagoya for nylon, Ehime for carbon fiber; generic textile/polymer records unchanged | FRN-9C546CCC918C61 has multiple relevant Japanese plants. Nagoya/Ehime are source-backed for nylon/carbon, but textile/velcro/generic polymer records need grade-level traceability. | Use Nagoya/Ehime only for matching records; require material grade for the rest. |

## Limite de lecture

Ces corrections remplacent des HQ, villes ou fallbacks par des sites industriels source-backed quand c'est raisonnable pour la simulation. Elles ne prouvent pas que le programme siège achète effectivement depuis ce site : cette preuve reste le certificat matière, la BOM, le PN, l'AVL ou la donnée achat/logistique.
