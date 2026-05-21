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
| Toray Industries | tier3_first_transformation | 49 | source_backed_site | Keep unresolved until PN/BOM/routing/material grade is available. |
| Mitsubishi Chemical | tier4_raw_material | 21 | fallback_site_needs_source | Keep unresolved until PN/BOM/routing/material grade is available. |
| XPO Logistic | logistics | 16 | source_backed_city_or_hq | Keep unresolved until PN/BOM/routing/material grade is available. |
| TE Connectivity | tier1 | 1 | source_backed_city_or_hq | Keep unresolved until PN/BOM/routing/material grade is available. |

## Site candidates requiring certificate/BOM validation

| node | retained site | occurrences | confidence | source |
|---|---|---:|---|---|
| Tata Steel | Tata Steel Jamshedpur Works | 86 | medium_high | https://www.tatasteel.com/contact-us/ |
| China Baowu / Baosteel | Baosteel Baoshan / Fujin Road site | 44 | medium | https://craft.co/baosteel/locations |
| ArcelorMittal | ArcelorMittal Industeel Le Creusot | 43 | medium | https://industeel.arcelormittal.com/legal-mentions/ |
| Aluminium Corporation of China / Chalco | Chalco Qinghai Branch / Beichuan Industrial Park | 42 | medium | https://www.chalco.com/en/sctxen/cpzsen/202012/t20201215_66289.html |
| Nucor Corp | Nucor Steel Berkeley | 42 | medium_high | https://enviro.epa.gov/triexplorer/release_fac_profile?TRI=29450NCRST1455H |

## Approximate but source-backed geocodes

| node | retained site | occurrences | status |
|---|---|---:|---|
| Huddersfield Textiles | Huddersfield Textiles Old Dye Works showroom / company site | 29 | source_backed_site_postcode |
| Shin-Etsu Silicones | Shin-Etsu Chemical Gunma Complex Isobe Plant | 2 | source_backed_industrial_site_nearby_geocode |
| Silicone Engineering | Silicone Engineering Blackburn | 2 | source_backed_industrial_site_nearby_geocode |
| Daio Paper Corporation | Daio Paper Mishima Mill | 1 | source_backed_industrial_site_city_geocode |
| Toray Industries | Toray Ehime Plant | 1 | source_backed_industrial_site_nearby_station_geocode |
| Toray Industries | Toray Ehime Plant | 1 | source_backed_industrial_site_nearby_station_geocode |
