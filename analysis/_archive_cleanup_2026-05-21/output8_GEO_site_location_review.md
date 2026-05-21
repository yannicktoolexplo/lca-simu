# Site-grade location review - output8_GEO

- Input: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_business_reviewed.json`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_site_reviewed.json`
- Change log: `C:/dev/lca-simu/analysis/output8_GEO_site_location_review_changes.csv`
- Applied record-level changes: **524**
- Source-backed fix rules: **20**

## Corrections appliquees

| fix_id | site retenu | occurrences | confiance | source | action simulation |
|---|---:|---:|---|---|---|
| SITE_TATA_JAMSHEDPUR | Tata Steel Jamshedpur Works | 86 | medium_high | https://www.tatasteel.com/contact-us/ | Use Jamshedpur Works as steel mill candidate; keep certificate validation required. |
| SITE_DUPONT_SPRUANCE | DuPont Spruance Manufacturing Site | 61 | high | https://www.dupont.co.jp/locations/dupont-spruance-manufacturing-site.html | Replace Wilmington HQ fallback with Spruance manufacturing site for DuPont fiber/polymer exposure. |
| SITE_BAOSTEEL_BAOSHAN | Baosteel Baoshan / Fujin Road site | 44 | medium | https://craft.co/baosteel/locations | Use Baoshan/Fujin Road as China steel mill candidate; require certificate for active allocation. |
| SITE_ARCELORMITTAL_INDUSTEEL | ArcelorMittal Industeel Le Creusot | 43 | medium | https://industeel.arcelormittal.com/legal-mentions/ | Use Industeel Le Creusot as special-steel scenario candidate; certificate required before hard allocation. |
| SITE_AUBERT_ANCIZES | Aubert & Duval Les Ancizes | 43 | high | https://www.space-aero.org/en/member/aubert-duval-les-ancizes/ | Replace Aubiere/Clermont fallback with Les Ancizes metallurgical site. |
| SITE_CHALCO_QINGHAI | Chalco Qinghai Branch / Beichuan Industrial Park | 42 | medium | https://www.chalco.com/en/sctxen/cpzsen/202012/t20201215_66289.html | Replace Beijing fallback with Qinghai smelter candidate; keep allocation validation required. |
| SITE_HINDALCO_RENUKOOT | Hindalco Renukoot | 42 | high | https://www.hindalco.com/about-us/manufacturing/renukoot | Replace Mumbai corporate fallback with Renukoot aluminium plant. |
| SITE_NUCOR_BERKELEY | Nucor Steel Berkeley | 42 | medium_high | https://enviro.epa.gov/triexplorer/release_fac_profile?TRI=29450NCRST1455H | Replace Charlotte HQ fallback with Nucor Berkeley mill candidate. |
| SITE_ALCOA_WARRICK | Alcoa Warrick Operations | 34 | high | https://www.alcoa.com/global/en/pdf/Alcoa-Warrick-Fact-Sheet.pdf | Replace Pittsburgh fallback with Warrick primary aluminium operation. |
| SITE_CONSTELLIUM_ISSOIRE | Constellium Issoire | 31 | high | https://www.constellium.com/fr/sites-de-production/issoire | Replace Voreppe R&D fallback with Issoire aerospace production site. |
| SITE_HUDDERSFIELD_TEXTILES | Huddersfield Textiles Old Dye Works showroom / company site | 29 | medium | https://www.huddersfieldtextiles.com/contact/ | Replace town centroid with company postcode-level site; validate mill/weaver before production allocation. |
| SITE_TORAY_NAGOYA_NYLON | Toray Nagoya Plant | 10 | high_for_nylon_only | https://www.toray.com/sustainability/activity/environment/data.html | Use Nagoya for Toray nylon records only; keep generic textile/composite Toray records unchanged unless grade is known. |
| SITE_MITSUBISHI_TIELT_ERTALON | Mitsubishi Chemical Advanced Materials Tielt | 7 | high_for_ertalon_only | https://eu.mitsubishi-chemical.com/locations/ | Use Tielt for Ertalon/MCAM records; keep non-Ertalon Mitsubishi records unchanged. |
| SITE_SHINETSU_GUNMA_ISOBE | Shin-Etsu Chemical Gunma Complex Isobe Plant | 2 | medium_high | https://www.shinetsu.co.jp/en/company/network/plant/ | Replace Tokyo HQ/city fallback with Gunma silicone plant area. |
| SITE_SILICONE_ENGINEERING_BLACKBURN | Silicone Engineering Blackburn | 2 | medium_high | https://ukgsassociation.co.uk/member/silicone-engineering-ltd/ | Replace Blackburn city point with Blakewater Road/Greenbank Business Park area. |
| SITE_TORAY_EHIME_CARBON | Toray Ehime Plant | 2 | medium_high | https://www.toray.co.jp/saiyou/fresh/worklifebalance/plants_ehime.html | Use Ehime for carbon-fiber record; exact gate coordinate can be refined later. |
| SITE_DAIO_MISHIMA | Daio Paper Mishima Mill | 1 | medium | https://www.daio-paper.co.jp/en/company/base/ | Replace generic Shikokuchuo city note with Mishima Mill site identity; improve coordinates if local geocoder available. |
| SITE_KEMCO_STLOUIS | Kemco/Mastercraft Building 1 | 1 | high | https://kemcoaerospace.com/about/locations/ | Replace St. Louis city fallback with Kemco/Mastercraft building. |
| SITE_LIEBHERR_LINDENBERG | Liebherr-Aerospace Lindenberg GmbH | 1 | high | https://www.liebherr.com/de-de/firmengruppe/standort/lindenberg-profil-3705432 | Replace Lindenberg city fallback with the Liebherr site address. |
| SITE_NORDIC_SAFFLE | Nordic Paper Saffle Mill | 1 | high | https://www.nordic-paper.com/en/about-us/production-units | Replace multi-mill fallback with Saffle mill for this paper/padding scenario. |

## Decisions non appliquees ou partielles

| fournisseur | decision | candidat | raison | action simulation |
|---|---|---|---|---|
| XPO Logistic | not_applied | XPO Europe HQ, 192 Avenue Thiers, Lyon, France, or route-specific XPO operating center | XPO logistics nodes should be modeled as route legs/hubs, not as a supplier plant. Public data does not identify the actual route hub for these records. | Keep as logistics provider; require route lane or hub assignment before replacing Greenwich/Lyon HQ. |
| TE Connectivity | not_applied | TE Connectivity Aerospace, Defense & Marine, Middletown, PA candidate | TE has AD&M operations but the exact cable/bracket part number is missing; a plant assignment would be false precision. | Keep Berwyn/HQ candidate inactive for site simulation until PN/BOM/AVL is available. |
| Mitsubishi Chemical | partial_only | Mitsubishi Chemical Advanced Materials Tielt applied only for Ertalon records | Non-Ertalon Mitsubishi records include nylon, LCD/display and generic molded plastic; public data is insufficient to allocate all to Tielt. | Use Tielt only for Ertalon; require grade/PN for other Mitsubishi records. |
| Toray Industries | partial_only | Nagoya for nylon, Ehime for carbon fiber; generic textile/polymer records unchanged | Toray has multiple relevant Japanese plants. Nagoya/Ehime are source-backed for nylon/carbon, but textile/velcro/generic polymer records need grade-level traceability. | Use Nagoya/Ehime only for matching records; require material grade for the rest. |

## Limite de lecture

Ces corrections remplacent des HQ, villes ou fallbacks par des sites industriels source-backed quand c'est raisonnable pour la simulation. Elles ne prouvent pas que le programme siège achète effectivement depuis ce site : cette preuve reste le certificat matière, la BOM, le PN, l'AVL ou la donnée achat/logistique.
