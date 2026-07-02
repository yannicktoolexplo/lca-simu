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

- `SRC_JAMCO_001` - JAMCO Aircraft Interiors Corporation (official_company): Japan; 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan; role: aircraft interiors manufacturer; source: https://www.jamco.co.jp/en/company/group.html
- `SRC_MGR_001` - MGR Foamtex Ltd (official_company): United Kingdom; DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK; role: aircraft passenger upholstery / foam systems supplier; source: https://www.mgrfoamtex.com/contact-us
- `SRC_LAUAK_001` - Groupe LAUAK (official_company): France; 2245 Route de Minhotz, 64240 Hasparren, France; role: aerostructures / sheet metal / machining / structural assembly supplier; source: https://www.groupe-lauak.com/lauak-groupe/presentation-du-groupe/sites/
- `SRC_PLASTISERVICE_001` - Plastiservice Charleroi (official_company): Belgium; ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium; role: plastics materials / processing supplier; source: https://plastiservice.com/nos-implantations/
- `SRC_JCAERO_001` - J&C Aero (official_company): Lithuania; Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279; role: aircraft interior / CAMO solutions provider; source: https://e.jcaero.com/contactus
- `SRC_STELIA_AIRBUS_001` - STELIA Aerospace / Airbus Atlantic cabin interior activity (official_group): France; Rochefort, France; role: premium passenger seat brand / Airbus Atlantic cabin interior activity; source: https://www.airbus.com/fr/products-services/commercial-aircraft/airframes/airbus-atlantic/amenagement-cabine
- `SRC_SAFRAN_SEATS_001` - Safran Seats (official_group): France / United States / United Kingdom depending site; Headquarters: 61 Rue Pierre Curie, 78373 Plaisir, France; other Safran Seats sites listed by Safran.; role: seat manufacturer; also customer/internal group in this dataset context; source: https://www.safran-group.com/locations
- `SRC_FIGEAC_001` - Figeac Aero (official_company): France; Zone industrielle de l'Aiguille, 46100 Figeac, France; role: aerostructures / metal transformation / assemblies supplier; source: https://www.figeac-aero.com/fr/contact
- `SRC_GATTEFIN_001` - ETS Gattefin (official_company): France; 201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France; role: precision machining / large-dimension machining supplier; source: https://gattefin.fr/
- `SRC_SEGNERE_001` - Groupe Segnere / SEGNERE Ade (industry_association): France; Z.I. du Toulicou, Ade, Occitanie 65100, France; role: precision mechanics / sheet metal / structural assembly supplier; source: https://www.space-aero.org/en/member/segnere-ade/
- `SRC_CELSO_001` - Celso SAS (official_company): France; 200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France; role: foam / cellular materials transformer; aeronautic aviation applications; source: https://celso.fr/en/contact-us/
- `SRC_ACH_001` - ACH (official_company): France; 16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France; role: aircraft interior upholstery / seats / foams supplier; source: https://www.ach-aeronefs.fr/en/contact/
- `SRC_EXSTO_001` - EXSTO Groupe France / Baule-Exsto Polymere (official_company): France; 55 avenue de la Deportation, 26100 Romans-sur-Isere, France; role: technical polymer / polyurethane supplier; source: https://www.exsto.com/en/contact
- `SRC_ANCRA_001` - Ancra International / Ancra Aircraft (official_company): USA; 601 S Vincent Ave, Azusa, CA 91702, United States of America; role: cargo restraint / fittings / straps / aircraft systems supplier; source: https://ancraaircraft.com/about-us/
- `SRC_TA_001` - TA Aerospace (official_company): USA; Valencia, California, USA - verify exact site address before geocoding; role: aerospace clamps / thermal insulation / engineered solutions supplier; source: https://www.taaerospace.com/
- `SRC_E2IP_001` - e2ip technologies (official_company): Canada; 1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada; role: electronics / HMI / electromechanical systems supplier; source: https://e2ip.com/contact/
- `SRC_THYSSEN_001` - thyssenkrupp Materials France / thyssenkrupp Aerospace (official_company): France; Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France; role: materials distributor / aerospace supply chain service provider, not raw material extractor; source: https://www.thyssenkrupp-aerospace.com/en/company/locations/france
- `SRC_EURALLIAGE_001` - Euralliage Ile de France (official_company): France; 3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France; role: non-ferrous metals stockist / trader / cutting service, not raw material extractor; source: https://www.euralliage.com/coordonnees.htm
- `SRC_TATA_STEEL_001` - Tata Steel (official_group): India; India operations include Jamshedpur, Gamharia, Kalinganagar and Meramandali; choose site based on product flow.; role: steel producer / upstream material producer; source: https://www.tata.com/business/tata-steel

## Corrections sourcees les plus importantes

- **JAMCO**: Toutes les lignes Jamco declarees France, Angleterre, Airbus Atlantique ou vides doivent etre corrigees vers Japan/Niigata si l entree vise JAMCO Aircraft Interiors. Les coordonnees France/UK associees a Jamco sont incoherentes.
- **MGR Foamtex**: Toutes les lignes MGR Foamtex declarees France, Japon ou `s` doivent etre corrigees vers United Kingdom/Thame; garder le site UK comme site fournisseur sauf preuve d un autre site.
- **Lauak**: Les lignes Lauak declarees Thailand/Pologne/`s` alors que la source et la query pointent Hasparren doivent etre ramenees a France/Hasparren, ou bien marquees `site_to_confirm` si une filiale non francaise etait intentionnelle.
- **Plastiservice**: Les lignes Plastiservice (Belgique) (France) utilisant Charleroi doivent etre corrigees vers Belgium/Charleroi.
- **J&C Aero**: Les lignes J&C Aero France/Airbus Atlantique ou coordonnees hors pays doivent etre corrigees vers Lithuania/Vilnius.
- **STELIA/Airbus Atlantic**: `Airbus Atlantique` ne doit pas etre une localisation. Utiliser supplier_group=Airbus Atlantic, brand=STELIA Aerospace, country=France, site=Rochefort si aucun autre site n est prouve.
- **Safran**: Les lignes Safran en Tier 1 doivent etre sorties de la liste fournisseurs externes et reclassees internal_site/internal_flow sauf confirmation achats d un flux intra-groupe.
- **thyssenkrupp/Euralliage**: Ces acteurs sont des distributeurs/stockistes/transformateurs matiere; ne pas les classer raw_material extractor sans preuve amont.

## Regles de correction par categorie

### MISSING_SUPPLIER_TIER (713)
- R1; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.
- R2; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.
- R3; supplier=-; status=data_source_required; sources=none; action=Complete the missing tier from purchasing/material traceability data. If no source exists, store explicit unknown object with reason rather than an empty silent list.

### COUNTRY_CENTROID_USED (595)
- R1; supplier=Euralliage; status=geocode_required; sources=SRC_EURALLIAGE_001; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.
- R1; supplier=Thyssen group; status=geocode_required; sources=SRC_THYSSEN_001; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.
- R1; supplier=Aluminium Corporation of China; status=geocode_required; sources=none; action=Do not treat country centroid as supplier-site coordinates. Re-geocode the verified site address; keep centroid only as fallback with geocode_precision=country_centroid.

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
- R1; supplier=Austria metall; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R1; supplier=Hindalco; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R1; supplier=Aluminium Corporation of China; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.

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
- R24; supplier=Jamco Corp (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R25; supplier=Jamco (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R30; supplier=Jamco Corp (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### COORDINATE_OUTSIDE_LOCATION_COUNTRY (43)
- R3; supplier=DuPont de Nemours; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R11; supplier=Nordic Paper Oyj; status=needs_source; sources=none; action=Normalize location into structured fields country_iso2/country/region/city/site_name. Re-geocode from a verified site address; do not infer coordinates from supplier name only.
- R24; supplier=Jamco Corp (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### COUNTRY_FIELD_LOCATION_MISMATCH (40)
- R24; supplier=Jamco Corp (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R25; supplier=Jamco (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R30; supplier=Jamco Corp (Japon) (France); status=source_backed_correction; sources=SRC_JAMCO_001; action=Normalize supplier to JAMCO Aircraft Interiors Corporation; set country/location to Japan and use verified site address: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan. Recompute lat/lon from this address and preserve old coordinates in audit history.

### TIER1_SELF_OR_CUSTOMER_AS_SUPPLIER (27)
- R44; supplier=SAFRAN(France); status=schema_fix_with_business_validation; sources=SRC_SAFRAN_SEATS_001; action=Safran appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.
- R67; supplier=SAFRAN(France); status=schema_fix_with_business_validation; sources=SRC_SAFRAN_SEATS_001; action=Safran appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.
- R77; supplier=SAFRAN - Filiale SeatNet (France); status=schema_fix_with_business_validation; sources=SRC_SAFRAN_SEATS_001; action=Safran appears to be the user/customer or internal group. Move this row from external tier1 to internal_site/internal_flow unless the purchasing source confirms an intra-group supplier relationship.

### LOCATION_INVALID (22)
- R39; supplier=Figeac Aéro (France) (s); status=source_backed_correction; sources=SRC_FIGEAC_001; action=Normalize supplier to Figeac Aero; set country/location to France and use verified site address: Zone industrielle de l'Aiguille, 46100 Figeac, France. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R40; supplier=Figeac Aéro (France) (s); status=source_backed_correction; sources=SRC_FIGEAC_001; action=Normalize supplier to Figeac Aero; set country/location to France and use verified site address: Zone industrielle de l'Aiguille, 46100 Figeac, France. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R63; supplier=Lauak Group (France) (s); status=source_backed_correction; sources=SRC_LAUAK_001; action=Normalize supplier to Groupe LAUAK; set country/location to France and use verified site address: 2245 Route de Minhotz, 64240 Hasparren, France. Recompute lat/lon from this address and preserve old coordinates in audit history.

### SUPPLIER_NAME_MALFORMED (16)
- R1; supplier=ESPACE (France)*; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.
- R1; supplier=Constellium (France; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.
- R2; supplier=Aubert&Duval (France)*; status=data_cleaning; sources=none; action=Clean supplier name: remove markers, fix parentheses, move descriptive text to notes, keep country/site in structured location fields.

### SAME_SUPPLIER_ASSIGNED_TO_MULTIPLE_TIERS (13)
- R1; supplier=Thyssen group; status=source_backed_correction; sources=SRC_THYSSEN_001; action=Keep this supplier as a material distributor/transformer, not raw_material extractor. Remove duplicated raw_material entry unless traceability proves upstream production.
- R2; supplier=Thyssen group; status=source_backed_correction; sources=SRC_THYSSEN_001; action=Keep this supplier as a material distributor/transformer, not raw_material extractor. Remove duplicated raw_material entry unless traceability proves upstream production.
- R3; supplier=DuPont de Nemours; status=needs_business_validation; sources=none; action=Resolve tier ownership from purchasing flow: Tier 1 direct supplier vs material transformer vs raw material producer. Remove copied duplicates across tiers.

### DUPLICATE_SUPPLIER_SAME_TIER (12)
- R189; supplier=segnere aero SAS (France); status=dedupe_rule; sources=SRC_SEGNERE_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.
- R189; supplier=GATTEFIN (France); status=dedupe_rule; sources=SRC_GATTEFIN_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.
- R189; supplier=Celso (France); status=dedupe_rule; sources=SRC_CELSO_001; action=Deduplicate within the same record/tier using canonical supplier_id + site_id + role. Merge primary flag, source IDs and transport legs.

### SYSTEM_SPELLING_NORMALIZATION (10)
- R237; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.
- R238; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.
- R239; supplier=-; status=data_cleaning; sources=none; action=Normalize spelling/accents in controlled vocabulary, e.g. Siege/Si?ge, and store display label separately if needed.

### TRANSPORT_MODE_NOT_A_TRANSPORT_MODE (5)
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.
- R6; supplier=-; status=schema_fix; sources=none; action=Remove non-mode values such as company names, internal flow labels or nan from modes. Store logistics provider/internal flags in separate fields.

### GEOCODE_PROVIDER_MISSING (3)
- R50; supplier=Ancra Aircraft (Californie - USA); status=source_backed_correction; sources=SRC_ANCRA_001; action=Normalize supplier to Ancra International; set country/location to USA and use verified site address: 601 S Vincent Ave, Azusa, CA 91702, United States of America. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R191; supplier=MGR FOAMTEX (Angleterre) (s); status=source_backed_correction; sources=SRC_MGR_001; action=Normalize supplier to MGR Foamtex Ltd; set country/location to United Kingdom and use verified site address: DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK. Recompute lat/lon from this address and preserve old coordinates in audit history.
- R209; supplier=Ancra Aircraft (Californie - USA); status=source_backed_correction; sources=SRC_ANCRA_001; action=Normalize supplier to Ancra International; set country/location to USA and use verified site address: 601 S Vincent Ave, Azusa, CA 91702, United States of America. Recompute lat/lon from this address and preserve old coordinates in audit history.

### DATASET_PRIMARY_MATERIAL_EMPTY (1)
- DATASET; supplier=-; status=schema_fix; sources=none; action=Remove primary_material if unused, or populate it from material model references. Empty field on all records is misleading.

### DATASET_MASS_ALL_ZERO (1)
- DATASET; supplier=-; status=data_source_required; sources=none; action=Reload mass from the seat BOM, PLM export or weighing source. If unknown, set mass_kg=null and mass_status=missing; do not keep 0.0 as a real value.

### DATASET_MARKET_SHARE_EMPTY (1)
- DATASET; supplier=-; status=data_source_required; sources=none; action=Reload market share as numeric 0-100 or set null with market_share_status=missing. Empty string should not be used for a numeric field.

### EMPTY_SYSTEM_OR_COMPONENT (1)
- R16; supplier=-; status=data_source_required; sources=none; action=Remove empty record or reconnect it to the original BOM row before export. It cannot be used for supply modeling.

## Limites

- Une source web confirme une existence, une adresse ou un role fournisseur; elle ne prouve pas automatiquement que ce site est celui utilise dans la supply chain Safran. Les corrections de site doivent etre validees contre donnees achats, contrats, ASN, certificats qualite ou traceabilite matiere.
- Les masses, parts de marche, tiers manquants et transports amont ne peuvent pas etre corriges par web research seule; ils demandent BOM/PLM/ERP/logistique.
- Les coordonnees doivent etre regenerees depuis les adresses validees; le fichier propose des adresses de reference mais ne remplace pas un geocodage qualifie.
