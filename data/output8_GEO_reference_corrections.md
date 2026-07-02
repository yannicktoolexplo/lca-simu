# Reference corrections sourcees - output8_GEO.json

Ce fichier relie les erreurs de `output8_GEO_audit_findings.csv` a des corrections proposees et, quand disponible, a une source metier. Le JSON source n a pas ete modifie.

## Fichiers

- Corrections detaillees: `data/output8_GEO_reference_corrections.csv`
- Registre des sources: `data/output8_GEO_reference_sources.csv`
- Audit d origine: `data/output8_GEO_audit_findings.csv`

## Couverture

- Lignes d audit reprises: 3157
- Severites audit: HIGH=428, LOW=579, MEDIUM=2150
- Statuts de correction: data_source_required=1917, geocode_required=595, source_backed_correction=274, schema_fix=171, needs_source=125, schema_fix_with_business_validation=27, data_cleaning=26, dedupe_rule=12, needs_business_validation=10
- Lignes avec source metier directe: 636
- Lignes sans source directe, a traiter par regle/schema/BOM/logistique: 2521

## Sources metier retenues

- `SRC_JAMCO_001` - FRN-B4560E9BC77D2B (official_company): Japan; 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan; role: aircraft interiors manufacturer; source: https://sources.invalid/FRN-1E9DB09C4FE35C/27d6c9719cd5b607
- `SRC_MGR_001` - FRN-213AAC10F8FF68 (official_company): United Kingdom; DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK; role: aircraft passenger upholstery / foam systems supplier; source: https://sources.invalid/FRN-213AAC10F8FF68/b35963cfb89ecaa9
- `SRC_LAUAK_001` - FRN-C1DF555DA868BF (official_company): France; 2245 Route de Minhotz, 64240 Hasparren, France; role: aerostructures / sheet metal / machining / structural assembly supplier; source: https://sources.invalid/FRN-C1DF555DA868BF/84469f6de2ef2075
- `SRC_FRN-D16128C2D1AA8B_001` - FRN-6DA33580D77667 (official_company): Belgium; ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium; role: plastics materials / processing supplier; source: https://sources.invalid/FRN-6DA33580D77667/0aa01c2bc1c764f4
- `SRC_JCAERO_001` - FRN-2EC56F8EB8EC02 (official_company): Lithuania; Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279; role: aircraft interior / CAMO solutions provider; source: https://sources.invalid/FRN-2EC56F8EB8EC02/da136f17c3e151ba
- `SRC_FRN-4F3EF5C6442315_FRN-1045D929655FAF_001` - FRN-4F3EF5C6442315 (official_group): France; Rochefort, France; role: premium passenger seat brand / FRN-4F3EF5C6442315 cabin interior activity; source: https://sources.invalid/FRN-4F3EF5C6442315/6c542b1300158f44
- `SRC_FRN-AA08AEDDCB94EB_001` - FRN-AA08AEDDCB94EB (official_group): France / United States / United Kingdom depending site; Headquarters: 61 Rue Pierre Curie, 78373 Plaisir, France; other FRN-AA08AEDDCB94EB sites listed by FRN-F1F796DB13C8E2.; role: seat manufacturer; also customer/internal group in this dataset context; source: https://sources.invalid/FRN-AA08AEDDCB94EB/a3382db34064c23a
- `SRC_FIGEAC_001` - FRN-8461B2D08E3D4E (official_company): France; Zone industrielle de l'Aiguille, 46100 Figeac, France; role: aerostructures / metal transformation / assemblies supplier; source: https://sources.invalid/FRN-8461B2D08E3D4E/91da9e1ad71e7632
- `SRC_FRN-FCB0C890EFA2B8_001` - FRN-0B41BF5B9E4B4E (official_company): France; 201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France; role: precision machining / large-dimension machining supplier; source: https://sources.invalid/FRN-0B41BF5B9E4B4E/3edb20f3674cd12c
- `SRC_FRN-D0B6DB0F437592_001` - FRN-999053838C0E1C (industry_association): France; Z.I. du Toulicou, Ade, Occitanie 65100, France; role: precision mechanics / sheet metal / structural assembly supplier; source: https://sources.invalid/FRN-999053838C0E1C/dfaa5e460d73f239
- `SRC_FRN-67CD5F21738C93_001` - FRN-73FE254CB14818 (official_company): France; 200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France; role: foam / cellular materials transformer; aeronautic aviation applications; source: https://sources.invalid/FRN-73FE254CB14818/66f09a5e8ae14c77
- `SRC_FRN-72A8D622F0F88D_001` - FRN-72A8D622F0F88D (official_company): France; 16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France; role: aircraft interior upholstery / seats / foams supplier; source: https://sources.invalid/FRN-72A8D622F0F88D/324836d380be55e2
- `SRC_EXSTO_001` - FRN-84293FE4ADFD8D (official_company): France; 55 avenue de la Deportation, 26100 Romans-sur-Isere, France; role: technical polymer / polyurethane supplier; source: https://sources.invalid/FRN-33013E3321A5B5/2664e4021d8fa64d
- `SRC_ANCRA_001` - FRN-5BB9473F176CD6 (official_company): USA; 601 S Vincent Ave, Azusa, CA 91702, United States of America; role: cargo restraint / fittings / straps / aircraft systems supplier; source: https://sources.invalid/FRN-5BB9473F176CD6/820ae6a63963e7f0
- `SRC_TA_001` - FRN-4DC00ECEFB8526 (official_company): USA; Valencia, California, USA - verify exact site address before geocoding; role: aerospace clamps / thermal insulation / engineered solutions supplier; source: https://sources.invalid/FRN-4DC00ECEFB8526/175304c3b4cf9832
- `SRC_FRN-869E1A8BB344FD_001` - FRN-FD0761D13CF2C9 (official_company): Canada; 1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada; role: electronics / HMI / electromechanical systems supplier; source: https://sources.invalid/FRN-FD0761D13CF2C9/128ea21c477639ca
- `SRC_THYSSEN_001` - FRN-6F69420F958BBD (official_company): France; Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France; role: materials distributor / aerospace supply chain service provider, not raw material extractor; source: https://sources.invalid/FRN-8D94FBDCC3B3B5/219f77fbb72670ab
- `SRC_FRN-C3B826345B6812_001` - FRN-6EF3EF62BA6339 (official_company): France; 3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France; role: non-ferrous metals stockist / trader / cutting service, not raw material extractor; source: https://sources.invalid/FRN-6EF3EF62BA6339/ebbb89b3f29571fb
- `SRC_FRN-5AA9E59DA0B02F_001` - FRN-5AA9E59DA0B02F (official_group): India; India operations include Jamshedpur, Gamharia, Kalinganagar and Meramandali; choose site based on product flow.; role: steel producer / upstream material producer; source: https://sources.invalid/FRN-5AA9E59DA0B02F/82460ad4d7fb1be8

## Corrections sourcees les plus importantes

- **JAMCO**: Toutes les lignes Jamco declarees France, Angleterre, FRN-4F3EF5C6442315 ou vides doivent etre corrigees vers Japan/Niigata si l entree vise JAMCO Aircraft Interiors. Les coordonnees France/UK associees a Jamco sont incoherentes.
- **FRN-54423E8FD293B7**: Toutes les lignes FRN-54423E8FD293B7 declarees France, Japon ou `s` doivent etre corrigees vers United Kingdom/Thame; garder le site UK comme site fournisseur sauf preuve d un autre site.
- **Lauak**: Les lignes Lauak declarees Thailand/Pologne/`s` alors que la source et la query pointent Hasparren doivent etre ramenees a France/Hasparren, ou bien marquees `site_to_confirm` si une filiale non francaise etait intentionnelle.
- **FRN-D16128C2D1AA8B**: Les lignes FRN-D16128C2D1AA8B utilisant Charleroi doivent etre corrigees vers Belgium/Charleroi.
- **FRN-2EC56F8EB8EC02**: Les lignes FRN-2EC56F8EB8EC02 France/FRN-4F3EF5C6442315 ou coordonnees hors pays doivent etre corrigees vers Lithuania/Vilnius.
- **FRN-4F3EF5C6442315/FRN-4F3EF5C6442315**: `FRN-4F3EF5C6442315` ne doit pas etre une localisation. Utiliser supplier_group=FRN-4F3EF5C6442315, brand=FRN-4F3EF5C6442315, country=France, site=Rochefort si aucun autre site n est prouve.
- **FRN-F1F796DB13C8E2**: Les lignes FRN-F1F796DB13C8E2 en Tier 1 doivent etre sorties de la liste fournisseurs externes et reclassees internal_site/internal_flow sauf confirmation achats d un flux intra-groupe.
- **thyssenkrupp/FRN-C3B826345B6812**: Ces acteurs sont des distributeurs/stockistes/transformateurs matiere; ne pas les classer raw_material extractor sans preuve amont.

## Regles de correction par categorie

### MISSING_SUPPLIER_TIER (713)
- R1; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.
- R2; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.
- R3; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.

### COUNTRY_CENTROID_USED (595)
- R1; supplier=FRN-C3B826345B6812; status=geocode_required; sources=SRC_FRN-C3B826345B6812_001; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.
- R1; supplier=FRN-BD805D8D4EB65E; status=geocode_required; sources=SRC_THYSSEN_001; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.
- R1; supplier=FRN-7A25E45203FCC9; status=geocode_required; sources=none; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.

### TRANSPORT_MODES_EMPTY (475)
- R1; supplier=-; status=data_source_required; sources=none; action=Fill transport route legs from logistics assumptions. If unknown, set modes=null and route_status=missing; empty list should not imply zero transport.
- R2; supplier=-; status=data_source_required; sources=none; action=Fill transport route legs from logistics assumptions. If unknown, set modes=null and route_status=missing; empty list should not imply zero transport.
- R4; supplier=-; status=data_source_required; sources=none; action=Fill transport route legs from logistics assumptions. If unknown, set modes=null and route_status=missing; empty list should not imply zero transport.

### MASS_INVALID (247)
- R1; supplier=-; status=data_source_required; sources=none; action=Reload mass from the seat BOM, PLM export or weighing source. If unknown, set mass_kg=null and mass_status=missing; do not keep 0.0 as a real value.
- R2; supplier=-; status=data_source_required; sources=none; action=Reload mass from the seat BOM, PLM export or weighing source. If unknown, set mass_kg=null and mass_status=missing; do not keep 0.0 as a real value.
- R3; supplier=-; status=data_source_required; sources=none; action=Reload mass from the seat BOM, PLM export or weighing source. If unknown, set mass_kg=null and mass_status=missing; do not keep 0.0 as a real value.

### MARKET_SHARE_INVALID (247)
- R1; supplier=-; status=data_source_required; sources=none; action=Reload market share as numeric 0-100 or set null with market_share_status=missing. Empty string should not be used for a numeric field.
- R2; supplier=-; status=data_source_required; sources=none; action=Reload market share as numeric 0-100 or set null with market_share_status=missing. Empty string should not be used for a numeric field.
- R3; supplier=-; status=data_source_required; sources=none; action=Reload market share as numeric 0-100 or set null with market_share_status=missing. Empty string should not be used for a numeric field.

### LOCATION_NONSTANDARD_LABEL (237)
- R1; supplier=FRN-6C9C7F20179A2A; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R1; supplier=FRN-191F6AC0669F77; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R1; supplier=FRN-7A25E45203FCC9; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.

### RAW_MATERIALS_EMPTY (232)
- R16; supplier=-; status=data_source_required; sources=none; action=Populate raw_materials from component material classification, or set raw_materials_status=missing.
- R17; supplier=-; status=data_source_required; sources=none; action=Populate raw_materials from component material classification, or set raw_materials_status=missing.
- R18; supplier=-; status=data_source_required; sources=none; action=Populate raw_materials from component material classification, or set raw_materials_status=missing.

### TRANSPORT_MODE_COMBINED_OR_UNNORMALIZED (85)
- R6; supplier=-; status=schema_fix; sources=none; action=Split combined route strings into ordered legs with atomic modes: truck, rail, ship, air. Keep route sequence outside the modes list.
- R75; supplier=-; status=schema_fix; sources=none; action=Split combined route strings into ordered legs with atomic modes: truck, rail, ship, air. Keep route sequence outside the modes list.
- R76; supplier=-; status=schema_fix; sources=none; action=Split combined route strings into ordered legs with atomic modes: truck, rail, ship, air. Keep route sequence outside the modes list.

### COMPONENT_IS_NOT_A_MATERIAL_OR_PART (80)
- R4; supplier=-; status=schema_fix; sources=none; action=Move Transport/packaging pseudo-components into separate transport_leg or packaging_record tables. Do not model them as normal material/part components.
- R5; supplier=-; status=schema_fix; sources=none; action=Move Transport/packaging pseudo-components into separate transport_leg or packaging_record tables. Do not model them as normal material/part components.
- R9; supplier=-; status=schema_fix; sources=none; action=Move Transport/packaging pseudo-components into separate transport_leg or packaging_record tables. Do not model them as normal material/part components.

### GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH (51)
- R24; supplier=FRN-9B72BBB9F69F3D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R25; supplier=FRN-D7C9F5165C495D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R30; supplier=FRN-9B72BBB9F69F3D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### COORDINATE_OUTSIDE_LOCATION_COUNTRY (43)
- R3; supplier=FRN-0B3DAD918C8F64; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R11; supplier=FRN-128E1984F5AEF9; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R24; supplier=FRN-9B72BBB9F69F3D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### COUNTRY_FIELD_LOCATION_MISMATCH (40)
- R24; supplier=FRN-9B72BBB9F69F3D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R25; supplier=FRN-D7C9F5165C495D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R30; supplier=FRN-9B72BBB9F69F3D; status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to FRN-B4560E9BC77D2B; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### TIER1_SELF_OR_CUSTOMER_AS_SUPPLIER (27)
- R44; supplier=FRN-F1F796DB13C8E2; status=schema_fix_with_business_validation; sources=SRC_FRN-AA08AEDDCB94EB_001; action=FRN-F1F796DB13C8E2 appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.
- R67; supplier=FRN-F1F796DB13C8E2; status=schema_fix_with_business_validation; sources=SRC_FRN-AA08AEDDCB94EB_001; action=FRN-F1F796DB13C8E2 appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.
- R77; supplier=FRN-25A8C56CB9C639; status=schema_fix_with_business_validation; sources=SRC_FRN-AA08AEDDCB94EB_001; action=FRN-F1F796DB13C8E2 appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.

### LOCATION_INVALID (22)
- R39; supplier=FRN-8461B2D08E3D4E; status=source_backed_correction; sources=SRC_FIGEAC_001; action=Normalize supplier to FRN-8461B2D08E3D4E; set country/location to France and use verified site address: Zone industrielle de l'Aiguille, 46100 Figeac, France. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R40; supplier=FRN-8461B2D08E3D4E; status=source_backed_correction; sources=SRC_FIGEAC_001; action=Normalize supplier to FRN-8461B2D08E3D4E; set country/location to France and use verified site address: Zone industrielle de l'Aiguille, 46100 Figeac, France. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R63; supplier=FRN-C1DF555DA868BF; status=source_backed_correction; sources=SRC_LAUAK_001; action=Normalize supplier to FRN-C1DF555DA868BF; set country/location to France and use verified site address: 2245 Route de Minhotz, 64240 Hasparren, France. Recompute lat/lon from this address and preserve old coordinates in audit history.

### SUPPLIER_NAME_MALFORMED (16)
- R1; supplier=FRN-45A091671294B0; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.
- R1; supplier=FRN-798BE9ED657B85; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.
- R2; supplier=FRN-83186B5AEF84D8; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.

### SAME_SUPPLIER_ASSIGNED_TO_MULTIPLE_TIERS (13)
- R1; supplier=FRN-BD805D8D4EB65E; status=source_backed_correction; sources=SRC_THYSSEN_001; action=Keep this supplier as a material distributor/transformer, not raw_material extractor. Remove duplicated raw_material entry unless traceability proves upstream production.
- R2; supplier=FRN-BD805D8D4EB65E; status=source_backed_correction; sources=SRC_THYSSEN_001; action=Keep this supplier as a material distributor/transformer, not raw_material extractor. Remove duplicated raw_material entry unless traceability proves upstream production.
- R3; supplier=FRN-0B3DAD918C8F64; status=needs_business_validation; sources=none; action=Resolve tier ownership from purchasing flow: Tier 1 direct supplier vs material transformer vs raw material producer. Remove copied duplicates across tiers.

### DUPLICATE_SUPPLIER_SAME_TIER (12)
- R189; supplier=FRN-297CE635156764; status=dedupe_rule; sources=SRC_FRN-D0B6DB0F437592_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.
- R189; supplier=FRN-FCB0C890EFA2B8; status=dedupe_rule; sources=SRC_FRN-FCB0C890EFA2B8_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.
- R189; supplier=FRN-67CD5F21738C93; status=dedupe_rule; sources=SRC_FRN-67CD5F21738C93_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.

### SYSTEM_SPELLING_NORMALIZATION (10)
- R237; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.
- R238; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.
- R239; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.

### TRANSPORT_MODE_NOT_A_TRANSPORT_MODE (5)
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.

### GEOCODE_PROVIDER_MISSING (3)
- R50; supplier=FRN-5BB9473F176CD6; status=source_backed_correction; sources=SRC_ANCRA_001; action=Normalize supplier to FRN-51245894531FE9; set country/location to USA and use verified site address: 601 S Vincent Ave, Azusa, CA 91702, United States of America. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R191; supplier=FRN-54423E8FD293B7; status=source_backed_correction; sources=SRC_MGR_001; action=Normalize supplier to FRN-213AAC10F8FF68; set country/location to United Kingdom and use verified site address: DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R209; supplier=FRN-5BB9473F176CD6; status=source_backed_correction; sources=SRC_ANCRA_001; action=Normalize supplier to FRN-51245894531FE9; set country/location to USA and use verified site address: 601 S Vincent Ave, Azusa, CA 91702, United States of America. Recompute lat/lon from this address and preserve old coordinates in audit history.

### DATASET_PRIMARY_MATERIAL_EMPTY (1)
- DATASET; supplier=-; status=schema_fix; sources=none; action=Remove primary_material if unused, or populate it from material model references. Empty field on all records is misleading.

### DATASET_MASS_ALL_ZERO (1)
- DATASET; supplier=-; status=data_source_required; sources=none; action=Reload mass from the seat BOM, PLM export or weighing source. If unknown, set mass_kg=null and mass_status=missing; do not keep 0.0 as a real value.

### DATASET_MARKET_SHARE_EMPTY (1)
- DATASET; supplier=-; status=data_source_required; sources=none; action=Reload market share as numeric 0-100 or set null with market_share_status=missing. Empty string should not be used for a numeric field.

### EMPTY_SYSTEM_OR_COMPONENT (1)
- R16; supplier=-; status=data_source_required; sources=none; action=Remove empty record or reconnect it to the original BOM row before export. It cannot be used for supply modeling.

## Limites

- Une source web confirme une existence, une adresse ou un role fournisseur; elle ne prouve pas automatiquement que ce site est celui utilise dans la supply chain FRN-F1F796DB13C8E2. Les corrections de site doivent etre validees contre donnees achats, contrats, ASN, certificats qualite ou traceabilite matiere.
- Les masses, parts de marche, tiers manquants et transports amont ne peuvent pas etre corriges par web research seule; ils demandent BOM/PLM/ERP/logistique.
- Les coordonnees doivent etre regenerees depuis les adresses validees; le fichier propose des adresses de reference mais ne remplace pas un geocodage qualifie.
