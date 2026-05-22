# Audit output8_GEO_normalized.json

Source: `analysis/output8_GEO_normalized.json`
Records: 175
Supplier entries: 3866
Detailed findings: `analysis/output8_GEO_normalized_audit_findings.csv`

## Bilan court

Cette version est plus complete que `data/output8_GEO.json`: les fournisseurs sont aplatis avec `role_hint`, les transports amont ne sont plus vides, et les fournisseurs Jamco/J&C Aero/Lauak/etc. sont souvent mieux normalises. Elle reste toutefois non exploitable telle quelle pour un calcul robuste: parts de marche vides partout, masses encore nulles sur la majorite des records, roles vagues (`material`, `transformation`), multiples fournisseurs primaires par role, et beaucoup de coordonnees encore au centroide pays ou sans source de geocodage.

## Chiffres cles

- Findings: 3720 total; HIGH=386, MEDIUM=1925, LOW=1409
- Role hints: tier1=1522, tier3_first_transformation=787, tier2_second_transformation=550, tier4_raw_material=523, oem=235, material=128, logistics=64, transformation=57
- Geocode providers: cache:nominatim=1627, nominatim=1146, manual=886, (missing)=177, None=30
- Top locations: 'France'=1962, 'Allemagne'=322, 'Japan'=308, 'USA'=270, 'Inde'=176, 'Philippines'=154, 'Chine'=146, 'Japon'=107, 'Thailande'=77, 'Angleterre'=56, 'Luxembourg'=45, 'Lituanie'=36, 'Autriche'=33, 'États-Unis'=30, 'Californie - USA'=30, 'Pologne'=26, 'Canada'=25, 'Danemark'=15, 'Finlande'=11, 'Mexique'=8
- mass_kg=0.0 on 160/175 records; market_share_pct empty on 175/175 records.

## Categories

- LOCATION_NONSTANDARD_LABEL: 1092
- DUPLICATE_SUPPLIER_SAME_RECORD_ROLE: 569
- COUNTRY_CENTROID_USED: 382
- OEM_ENTRY_IN_SUPPLIERS_LIST: 235
- MULTIPLE_PRIMARY_SUPPLIERS_PER_ROLE: 230
- GEOCODE_PROVIDER_MISSING: 207
- COORDINATE_OUTSIDE_LOCATION_COUNTRY: 196
- ROLE_HINT_VAGUE: 185
- MARKET_SHARE_INVALID: 175
- RAW_MATERIALS_EMPTY: 163
- MASS_INVALID: 160
- LOGISTICS_PROVIDER_IN_SUPPLIERS_LIST: 64
- GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH: 21
- SYSTEM_SPELLING_NORMALIZATION: 18
- GEOCODE_QUERY_MULTIPLE_COUNTRIES: 12
- MISSING_ROLE_TIER1: 4
- TRANSPORT_MODE_NOT_A_TRANSPORT_MODE: 3
- SUPPLIER_NAME_MALFORMED: 2
- DATASET_MARKET_SHARE_EMPTY: 1
- DATASET_MASS_ZERO_REMAINING: 1

## Exemples prioritaires

### DATASET_MARKET_SHARE_EMPTY
- DATASET; role=; loc=->;  / : market_share_pct is an empty string on all records

### DATASET_MASS_ZERO_REMAINING
- DATASET; role=; loc=->;  / : mass_kg is 0.0 on 160/175 records

### MASS_INVALID
- R1; role=; loc=->; Ens. Equipements latéraux / A5086 - Aluminium: mass_kg should be positive, got 0.0
- R2; role=; loc=->; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): mass_kg should be positive, got 0.0
- R3; role=; loc=->; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: mass_kg should be positive, got 0.0
- R6; role=; loc=->; Ens. Stowage latéral / cuir: mass_kg should be positive, got 0.0
- R7; role=; loc=->; lightning / lightning: mass_kg should be positive, got 0.0
- R9; role=; loc=->; Stowage assemblé avec porte / Silicone: mass_kg should be positive, got 0.0
- R10; role=; loc=->; System IFE (In-Flight Entertainment) est un ensemble d'équipements et de logiciels qui permet aux passagers d'occuper leur temps à bord d'un avion. / System IFE boitier ref FJKL1-3K1100-01ATAB: mass_kg should be positive, got 0.0
- R11; role=; loc=->; Coussin ottoman / tissu: mass_kg should be positive, got 0.0
- R12; role=; loc=->; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL: mass_kg should be positive, got 0.0
- R13; role=; loc=->; Accoudoir allée / 30NCD6 (nickel-chrome- molibdene): mass_kg should be positive, got 0.0

### MULTIPLE_PRIMARY_SUPPLIERS_PER_ROLE
- R1; role=; loc=->; Ens. Equipements latéraux / A5086 - Aluminium: role 'tier1' has 6 primary suppliers: ['ESPACE', 'GATTEFIN', 'Segnere Aero SAS', 'MGA Villeneuve St Lot', 'SENIOR AEROSPACE', 'JV Group']
- R1; role=; loc=->; Ens. Equipements latéraux / A5086 - Aluminium: role 'oem' has 2 primary suppliers: ['SAFRAN', 'Safran']
- R6; role=; loc=->; Ens. Stowage latéral / cuir: role 'tier3_first_transformation' has 2 primary suppliers: ['La Filière Française du cuir', 'La Filière Française du cuir']
- R6; role=; loc=->; Ens. Stowage latéral / cuir: role 'tier1' has 2 primary suppliers: ['MGA Villeneuve St Lot', 'ACH']
- R7; role=; loc=->; lightning / lightning: role 'tier2_second_transformation' has 2 primary suppliers: ['Diodes Incorporated', 'E2IP']
- R8; role=; loc=->; Padding (rembourrage) / AIRVOLT LAMINAT: role 'tier2_second_transformation' has 2 primary suppliers: ['Group Mondi', 'MGR FOAMTEX']
- R9; role=; loc=->; Stowage assemblé avec porte / Silicone: role 'tier1' has 3 primary suppliers: ['General Electric', 'General Electric', 'MGA Villeneuve St Lot']
- R10; role=; loc=->; System IFE (In-Flight Entertainment) est un ensemble d'équipements et de logiciels qui permet aux passagers d'occuper leur temps à bord d'un avion. / System IFE boitier ref FJKL1-3K1100-01ATAB: role 'tier2_second_transformation' has 2 primary suppliers: ['BT Electronics', 'NVIDIA']
- R11; role=; loc=->; Coussin ottoman / tissu: role 'tier2_second_transformation' has 2 primary suppliers: ['DuPont de Nemours', 'FRANKLIN']
- R11; role=; loc=->; Coussin ottoman / tissu: role 'tier1' has 2 primary suppliers: ['GATTEFIN', 'MGA Villeneuve St Lot']

### COUNTRY_CENTROID_USED
- R1 S5 Aluminium Corporation of China; role=material; loc=Chine->China; Ens. Equipements latéraux / A5086 - Aluminium: coordinates are country centroid (China); not supplier/site precise
- R1 S25 Safran; role=oem; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: coordinates are country centroid (France); not supplier/site precise
- R2 S4 China Baowu; role=material; loc=Chine->China; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): coordinates are country centroid (China); not supplier/site precise
- R2 S14 Safran; role=oem; loc=France->France; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): coordinates are country centroid (France); not supplier/site precise
- R3 S1 Mitsubishi Chemical; role=tier4_raw_material; loc=Japon->Japan; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: coordinates are country centroid (Japan); not supplier/site precise
- R3 S12 Safran; role=oem; loc=France->France; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: coordinates are country centroid (France); not supplier/site precise
- R4 S12 Safran; role=oem; loc=France->France; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: coordinates are country centroid (France); not supplier/site precise
- R5 S3 China Baowu; role=material; loc=Chine->China; Bumper version porte / alliage Cu: coordinates are country centroid (China); not supplier/site precise
- R5 S14 Safran; role=oem; loc=France->France; Bumper version porte / alliage Cu: coordinates are country centroid (France); not supplier/site precise
- R6 S13 Safran; role=oem; loc=France->France; Ens. Stowage latéral / cuir: coordinates are country centroid (France); not supplier/site precise

### GEOCODE_PROVIDER_MISSING
- R1 S25 Safran; role=oem; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: geocode_provider is missing although coordinates may be present
- R2 S14 Safran; role=oem; loc=France->France; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): geocode_provider is missing although coordinates may be present
- R3 S12 Safran; role=oem; loc=France->France; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: geocode_provider is missing although coordinates may be present
- R4 S12 Safran; role=oem; loc=France->France; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: geocode_provider is missing although coordinates may be present
- R5 S14 Safran; role=oem; loc=France->France; Bumper version porte / alliage Cu: geocode_provider is missing although coordinates may be present
- R6 S13 Safran; role=oem; loc=France->France; Ens. Stowage latéral / cuir: geocode_provider is missing although coordinates may be present
- R7 S13 Safran; role=oem; loc=France->France; lightning / lightning: geocode_provider is missing although coordinates may be present
- R8 S15 Safran; role=oem; loc=France->France; Padding (rembourrage) / AIRVOLT LAMINAT: geocode_provider is missing although coordinates may be present
- R9 S15 Safran; role=oem; loc=France->France; Stowage assemblé avec porte / Silicone: geocode_provider is missing although coordinates may be present
- R10 S10 Safran; role=oem; loc=France->France; System IFE (In-Flight Entertainment) est un ensemble d'équipements et de logiciels qui permet aux passagers d'occuper leur temps à bord d'un avion. / System IFE boitier ref FJKL1-3K1100-01ATAB: geocode_provider is missing although coordinates may be present

### GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH
- R9 S13 Plastiservice; role=tier2_second_transformation; loc=France->France; Stowage assemblé avec porte / Silicone: geocode_query countries=['Belgium'] do not include normalized location=France
- R78 S20 Plastiservice; role=tier2_second_transformation; loc=France->France; Ecran - Screen Display (COTS) / Display, liquid crystal, 17 pouces: geocode_query countries=['Belgium'] do not include normalized location=France
- R79 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Accoudoir allée / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R80 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Ens. Stowage latéral / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R82 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Ensemble porte / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R83 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Ens. Tablette repas / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R84 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Stowage assemblé avec porte / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R85 S10 Plastiservice; role=tier2_second_transformation; loc=France->France; Structure ottoman horizontale / Ertalon: geocode_query countries=['Belgium'] do not include normalized location=France
- R111 S18 Plastiservice; role=tier2_second_transformation; loc=France->France; Ceinture de sécurité / nylon: geocode_query countries=['Belgium'] do not include normalized location=France
- R112 S18 Plastiservice; role=tier2_second_transformation; loc=France->France; Support clamps / nylon: geocode_query countries=['Belgium'] do not include normalized location=France

### COORDINATE_OUTSIDE_LOCATION_COUNTRY
- R3 S3 DuPont de Nemours; role=tier2_second_transformation; loc=USA->USA; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: lat/lon (47.7979001,7.190275) are outside normalized location country USA
- R3 S6 DuPont de Nemours; role=tier2_second_transformation; loc=USA->USA; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: lat/lon (47.7979001,7.190275) are outside normalized location country USA
- R8 S5 Nordic Paper Oyj; role=tier4_raw_material; loc=Finlande->Finland; Padding (rembourrage) / AIRVOLT LAMINAT: lat/lon (59.1400084,12.9178462) are outside normalized location country Finland
- R11 S1 DuPont de Nemours; role=tier2_second_transformation; loc=USA->USA; Coussin ottoman / tissu: lat/lon (47.7979001,7.190275) are outside normalized location country USA
- R12 S2 DuPont de Nemours; role=tier2_second_transformation; loc=USA->USA; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL: lat/lon (47.7979001,7.190275) are outside normalized location country USA
- R15 S17 Schroth; role=tier2_second_transformation; loc=USA->USA; Ens. Equipements latéraux / acier: lat/lon (51.1657,10.4515) are outside normalized location country USA
- R15 S18 J&C Aero; role=tier1; loc=Lituanie->Lithuania; Ens. Equipements latéraux / acier: lat/lon (-20.5228026,-54.6480379) are outside normalized location country Lithuania
- R15 S19 Anjou Aéro; role=tier1; loc=France->France; Ens. Equipements latéraux / acier: lat/lon (39.7837304,-100.4458825) are outside normalized location country France
- R45 S17 Schroth; role=tier2_second_transformation; loc=USA->USA; Ceinture de sécurité / acier: lat/lon (51.1657,10.4515) are outside normalized location country USA
- R45 S18 J&C Aero; role=tier1; loc=Lituanie->Lithuania; Ceinture de sécurité / acier: lat/lon (-20.5228026,-54.6480379) are outside normalized location country Lithuania

### ROLE_HINT_VAGUE
- R1 S3 Austria metall; role=transformation; loc=Autriche->Austria; Ens. Equipements latéraux / A5086 - Aluminium: role_hint 'transformation' is too vague; proposed canonical role: tier2_or_tier3_transformation
- R1 S5 Aluminium Corporation of China; role=material; loc=Chine->China; Ens. Equipements latéraux / A5086 - Aluminium: role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R2 S2 Arcelor Mittal; role=material; loc=Luxembourg->Luxembourg; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R2 S4 China Baowu; role=material; loc=Chine->China; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R5 S2 Arcelor Mittal; role=material; loc=Luxembourg->Luxembourg; Bumper version porte / alliage Cu: role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R5 S3 China Baowu; role=material; loc=Chine->China; Bumper version porte / alliage Cu: role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R11 S2 Zhejiang Yuxin Textile Co.,Ltd.; role=transformation; loc=Chine->China; Coussin ottoman / tissu: role_hint 'transformation' is too vague; proposed canonical role: tier2_or_tier3_transformation
- R12 S3 Zhejiang Yuxin Textile Co.,Ltd.; role=transformation; loc=Chine->China; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL: role_hint 'transformation' is too vague; proposed canonical role: tier2_or_tier3_transformation
- R13 S2 Arcelor Mittal; role=material; loc=Luxembourg->Luxembourg; Accoudoir allée / 30NCD6 (nickel-chrome- molibdene): role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation
- R13 S4 China Baowu; role=material; loc=Chine->China; Accoudoir allée / 30NCD6 (nickel-chrome- molibdene): role_hint 'material' is too vague; proposed canonical role: tier4_raw_material_or_tier3_first_transformation

### DUPLICATE_SUPPLIER_SAME_RECORD_ROLE
- R1 S6,10 Thyssen group; role=tier3_first_transformation; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: duplicate supplier ('thyssen group', 'tier3_first_transformation', 'France') at positions [6, 10]
- R1 S12,16 Figeac Aero; role=tier1; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: duplicate supplier ('figeac aero', 'tier1', 'France') at positions [12, 16]
- R1 S13,24 GATTEFIN; role=tier1; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: duplicate supplier ('gattefin', 'tier1', 'France') at positions [13, 24]
- R1 S20,21 JV Group; role=tier1; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: duplicate supplier ('jv group', 'tier1', 'France') at positions [20, 21]
- R1 S22,25 SAFRAN; role=oem; loc=France->France; Ens. Equipements latéraux / A5086 - Aluminium: duplicate supplier ('safran', 'oem', 'France') at positions [22, 25]
- R2 S5,9 Thyssen group; role=tier3_first_transformation; loc=France->France; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): duplicate supplier ('thyssen group', 'tier3_first_transformation', 'France') at positions [5, 9]
- R3 S3,6 DuPont de Nemours; role=tier2_second_transformation; loc=USA->USA; Ens. Equipements latéraux / Ertalon par moulage par injection plastique: duplicate supplier ('dupont de nemours', 'tier2_second_transformation', 'USA') at positions [3, 6]
- R6 S1,5 La Filière Française du cuir; role=tier3_first_transformation; loc=France->France; Ens. Stowage latéral / cuir: duplicate supplier ('la filiere francaise du cuir', 'tier3_first_transformation', 'France') at positions [1, 5]
- R6 S2,6 Maison Fichet; role=tier2_second_transformation; loc=France->France; Ens. Stowage latéral / cuir: duplicate supplier ('maison fichet', 'tier2_second_transformation', 'France') at positions [2, 6]
- R6 S3,7 EUREKA SARL DERAYGE SERVICE; role=tier2_second_transformation; loc=France->France; Ens. Stowage latéral / cuir: duplicate supplier ('eureka sarl derayge service', 'tier2_second_transformation', 'France') at positions [3, 7]

### TRANSPORT_MODE_NOT_A_TRANSPORT_MODE
- R6; role=; loc=->; Ens. Stowage latéral / cuir: to_first_transformation.modes contains non-mode value: Interne entreprise
- R76; role=; loc=->; Manchette acc. Mobile / cuir: to_first_transformation.modes contains non-mode value: Interne entreprise
- R77; role=; loc=->; Manchette équipée / cuir: to_first_transformation.modes contains non-mode value: Interne entreprise

## Priorites de correction

1. Remplacer les `mass_kg=0.0` restants par des masses BOM/PLM ou `null` + statut explicite.
2. Charger des `market_share_pct` numeriques ou remplacer les chaines vides par `null` + statut.
3. Normaliser `role_hint`: remplacer `material` et `transformation` par des roles canoniques (`tier2_second_transformation`, `tier3_first_transformation`, `tier4_raw_material`) selon le role fournisseur.
4. Resoudre les multiples `is_primary=true` par role: soit un seul primaire par role, soit des allocations/share explicites.
5. Regenerer les coordonnees depuis adresses site verifiees, et taguer les centroides pays comme fallback non site-grade.
6. Sortir `oem` et `logistics` de la liste fournisseurs externe si le modele aval attend uniquement des tiers supply.
7. Corriger les derniers conflits pays/query/coordonnees et les fournisseurs dupliques dans un meme record.
