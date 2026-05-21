# Site precision after review

- Scope: active records only; suppliers, OEM sites and logistics providers used by the map.
- Total map-positionable entries: **3144**.
- `country_centroid`: **0** occurrences, **0** unique nodes.
- `unresolved_hq_or_fallback`: **87** occurrences, **4** unique nodes.
- `site_candidate_requires_certificate`: **257** occurrences, **5** unique nodes.
- `approx_source_geocode`: **36** occurrences, **6** unique nodes.

## Remaining unresolved HQ/fallback nodes

| node | role | occurrences | status | action |
|---|---:|---:|---|---|
| FRN-0F56088BEA4986 | tier3_first_transformation | 49 | source_backed_site | Keep unresolved until PN/BOM/routing/material grade is available. |
| FRN-6378B78052F4FE | tier4_raw_material | 21 | fallback_site_needs_source | Keep unresolved until PN/BOM/routing/material grade is available. |
| FRN-7BCA1282BFEC03 | logistics | 16 | source_backed_city_or_hq | Keep unresolved until PN/BOM/routing/material grade is available. |
| FRN-B9C4C86C42C8B4 | tier1 | 1 | source_backed_city_or_hq | Keep unresolved until PN/BOM/routing/material grade is available. |

## Site candidates requiring certificate/BOM validation

| node | retained site | occurrences | confidence | source |
|---|---|---:|---|---|
| FRN-5AA9E59DA0B02F | FRN-5AA9E59DA0B02F Jamshedpur Works | 86 | medium_high | https://sources.invalid/FRN-5AA9E59DA0B02F/5592a987c0e8bf05 |
| FRN-CF71418802439F | Baosteel Baoshan / Fujin Road site | 44 | medium | https://sources.invalid/FRN-CF71418802439F/61e2b40f4124dc67 |
| FRN-3C5607FC501E5A | FRN-3C5607FC501E5A Industeel Le Creusot | 43 | medium | https://sources.invalid/FRN-3C5607FC501E5A/19f83839bed63ba0 |
| FRN-7A25E45203FCC9 | FRN-7A25E45203FCC9 Qinghai Branch / Beichuan Industrial Park | 42 | medium | https://sources.invalid/FRN-7A25E45203FCC9/8c2766000e43f27a |
| FRN-B8E884308EA449 | Nucor Steel Berkeley | 42 | medium_high | https://sources.invalid/FRN-B8E884308EA449/03613c032bda4791 |

## Approximate but source-backed geocodes

| node | retained site | occurrences | status |
|---|---|---:|---|
| FRN-0CA3DB5897A052 | FRN-0CA3DB5897A052 Old Dye Works showroom / company site | 29 | source_backed_site_postcode |
| FRN-332F92E4BA4B00 | Shin-Etsu Chemical Gunma Complex Isobe Plant | 2 | source_backed_industrial_site_nearby_geocode |
| FRN-BDE3FD68E4E87F | FRN-BDE3FD68E4E87F Blackburn | 2 | source_backed_industrial_site_nearby_geocode |
| FRN-B7600B824E7BC7 | FRN-B7600B824E7BC7 Mishima Mill | 1 | source_backed_industrial_site_city_geocode |
| FRN-0F56088BEA4986 | FRN-9C546CCC918C61 Ehime Plant | 1 | source_backed_industrial_site_nearby_station_geocode |
| FRN-0F56088BEA4986 | FRN-9C546CCC918C61 Ehime Plant | 1 | source_backed_industrial_site_nearby_station_geocode |
