# Audit output8_GEO.json

Source: `data/output8_GEO.json`
Records: 247
Supplier entries: 1118
Detailed findings: `data/output8_GEO_audit_findings.csv`

## Bilan court

Le JSON n est pas fiable tel quel pour un modele de supply chain de siege aeronautique: les donnees de masse et de parts de marche sont vides, la profondeur Tier est presque toujours absente apres Tier 1, et les localisations ne sont pas homogenes. Les erreurs les plus critiques sont les contradictions entre `location`, `country`, `lat/lon` et `geocode_query`, notamment sur Jamco, Lauak, FRN-54423E8FD293B7, FRN-D16128C2D1AA8B, FRN-2EC56F8EB8EC02 et plusieurs entrees FRN-4F3EF5C6442315/FRN-4F3EF5C6442315.

## Chiffres cles

- Constats generes: 3157 au total: HIGH=428, MEDIUM=2150, LOW=579.
- Entrees fournisseurs par tier: tier1=957, first_transformation=73, raw_material=88. `primary_material` est vide partout.
- Couverture tier: `tier1` vide pour 2 records; `first_transformation` vide pour 232/247; `raw_material` vide pour 232/247; `primary_material` vide pour 247/247.
- Geocodage: cache:nominatim=656, country_centroid=439, nominatim=20, (missing)=3. Le fichier contient 595 coordonnees detectees comme centroides de pays ou equivalentes.
- Donnees quantitatives: `mass_kg=0.0` sur 247/247 records; `market_share_pct=""` sur 247/247 records.
- Libelles de localisation les plus frequents: 'France'=789, 'USA'=55, 'Pologne'=55, 'Belgique'=42, 'Allemagne'=33, 'Thailande'=25, 'Japon'=23, 'Angleterre'=22, 's'=9, 'Inde'=8, 'Chine'=8, 'Thailand'=8, 'FRN-4F3EF5C6442315'=8, ''=5, 'Lituanie'=4, 'Californie - USA'=3, 'Autriche'=2, 'Luxembourg'=2.

## Categories

- MISSING_SUPPLIER_TIER: 713
- COUNTRY_CENTROID_USED: 595
- TRANSPORT_MODES_EMPTY: 475
- MASS_INVALID: 247
- MARKET_SHARE_INVALID: 247
- LOCATION_NONSTANDARD_LABEL: 237
- RAW_MATERIALS_EMPTY: 232
- TRANSPORT_MODE_COMBINED_OR_UNNORMALIZED: 85
- COMPONENT_IS_NOT_A_MATERIAL_OR_PART: 80
- GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH: 51
- COORDINATE_OUTSIDE_LOCATION_COUNTRY: 43
- COUNTRY_FIELD_LOCATION_MISMATCH: 40
- TIER1_SELF_OR_CUSTOMER_AS_SUPPLIER: 27
- LOCATION_INVALID: 22
- SUPPLIER_NAME_MALFORMED: 16
- SAME_SUPPLIER_ASSIGNED_TO_MULTIPLE_TIERS: 13
- DUPLICATE_SUPPLIER_SAME_TIER: 12
- SYSTEM_SPELLING_NORMALIZATION: 10
- TRANSPORT_MODE_NOT_A_TRANSPORT_MODE: 5
- GEOCODE_PROVIDER_MISSING: 3
- DATASET_PRIMARY_MATERIAL_EMPTY: 1
- DATASET_MASS_ALL_ZERO: 1
- DATASET_MARKET_SHARE_EMPTY: 1
- EMPTY_SYSTEM_OR_COMPONENT: 1

## Localisation

Problemes principaux: pays non normalises, pays contradictoires, organisations utilisees comme lieux, champs `country` incoherents et coordonnees hors pays declare.

### LOCATION_INVALID
- R39 tier1[4]; Manchette acc. Mobile / A5086 - Aluminium; supplier=FRN-8461B2D08E3D4E; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],2.0333182: location is not a usable country/location: 's'
- R40 tier1[4]; Manchette équipée / A5086 - Aluminium; supplier=FRN-8461B2D08E3D4E; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],2.0333182: location is not a usable country/location: 's'
- R63 tier1[4]; Manchette équipée / acier; supplier=FRN-C1DF555DA868BF; loc=s normalized=INVALID_S country=France lat/lon=[coordonnée retirée],2.2137: location is not a usable country/location: 's'
- R74 tier1[4]; Manchette acc. Mobile / Alu; supplier=FRN-8461B2D08E3D4E; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],2.0333182: location is not a usable country/location: 's'
- R147 tier1[5]; Ens. Equipements latéraux / packaging; supplier=FRN-67CD5F21738C93; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],-48.557608: location is not a usable country/location: 's'
- R148 tier1[5]; Ens. Equipements latéraux / Transport; supplier=FRN-67CD5F21738C93; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],-48.557608: location is not a usable country/location: 's'
- R189 tier1[7]; Manchette acc. Mobile / Transport; supplier=FRN-C1DF555DA868BF; loc=s normalized=INVALID_S country=France lat/lon=[coordonnée retirée],2.2137: location is not a usable country/location: 's'
- R190 tier1[7]; Manchette acc. Mobile / packaging; supplier=FRN-C1DF555DA868BF; loc=s normalized=INVALID_S country=France lat/lon=[coordonnée retirée],2.2137: location is not a usable country/location: 's'
- R191 tier1[5]; Manchette équipée / Transport; supplier=FRN-54423E8FD293B7; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],-0.966526: location is not a usable country/location: 's'
- R219 tier1[1]; Manchette équipée / velcro; supplier=FRN-72A8D622F0F88D; loc= normalized=INVALID_EMPTY country= lat/lon=[coordonnée retirée],-8.9608437: location is not a usable country/location: ''

### COUNTRY_FIELD_LOCATION_MISMATCH
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'
- R63 tier1[4]; Manchette équipée / acier; supplier=FRN-C1DF555DA868BF; loc=s normalized=INVALID_S country=France lat/lon=[coordonnée retirée],2.2137: country='France' conflicts with location='s'
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=FRN-C1DF555DA868BF; loc=Thailande normalized=Thailand country=France lat/lon=[coordonnée retirée],2.2137: country='France' conflicts with location='Thailande'
- R85 tier1[3]; Ens. Structure fauteuil / inox; supplier=FRN-C1DF555DA868BF; loc=Thailand normalized=Thailand country=France lat/lon=[coordonnée retirée],2.2137: country='France' conflicts with location='Thailand'
- R87 tier1[5]; Ens. Tablette repas / Ertalon; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: country='Japan' conflicts with location='France'

### GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=FRN-C1DF555DA868BF; loc=Thailande normalized=Thailand country=France lat/lon=[coordonnée retirée],2.2137: geocode_query countries=['France'] do not include normalized location=Thailand
- R80 tier1[3]; Manchette acc. Mobile / cuir; supplier=FRN-54423E8FD293B7; loc=France normalized=France country= lat/lon=[coordonnée retirée],-0.966526: geocode_query countries=['United Kingdom'] do not include normalized location=France
- R85 tier1[3]; Ens. Structure fauteuil / inox; supplier=FRN-C1DF555DA868BF; loc=Thailand normalized=Thailand country=France lat/lon=[coordonnée retirée],2.2137: geocode_query countries=['France'] do not include normalized location=Thailand
- R87 tier1[5]; Ens. Tablette repas / Ertalon; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: geocode_query countries=['Japan'] do not include normalized location=France

### COORDINATE_OUTSIDE_LOCATION_COUNTRY
- R3 first_transformation[3]; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=FRN-0B3DAD918C8F64; loc=Delaware - USA normalized=USA country= lat/lon=[coordonnée retirée],7.190275: lat/lon ([coordonnées retirées]) are outside normalized location country USA
- R11 raw_material[5]; Padding (rembourrage) / AIRVOLT LAMINAT; supplier=FRN-128E1984F5AEF9; loc=Finlande normalized=Finland country= lat/lon=[coordonnée retirée],12.9178462: lat/lon ([coordonnées retirées]) are outside normalized location country Finland
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R49 tier1[3]; Ceinture de sécurité / acier; supplier=FRN-2D3B1185B3FC0C; loc=Lituanie normalized=Lithuania country= lat/lon=[coordonnée retirée],-54.6480379: lat/lon ([coordonnées retirées]) are outside normalized location country Lithuania
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=FRN-9B72BBB9F69F3D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=FRN-D7C9F5165C495D; loc=France normalized=France country=Japan lat/lon=[coordonnée retirée],138.2529: lat/lon ([coordonnées retirées]) are outside normalized location country France
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=FRN-C1DF555DA868BF; loc=Thailande normalized=Thailand country=France lat/lon=[coordonnée retirée],2.2137: lat/lon ([coordonnées retirées]) are outside normalized location country Thailand

### GEOCODE_PROVIDER_MISSING
- R50 tier1[2]; Support clamps / acier; supplier=FRN-5BB9473F176CD6; loc=Californie - USA normalized=USA country= lat/lon=[coordonnée retirée],-117.92529: geocode_provider is missing although coordinates are present
- R191 tier1[5]; Manchette équipée / Transport; supplier=FRN-54423E8FD293B7; loc=s normalized=INVALID_S country= lat/lon=[coordonnée retirée],-0.966526: geocode_provider is missing although coordinates are present
- R209 tier1[3]; Support clamps / packaging; supplier=FRN-5BB9473F176CD6; loc=Californie - USA normalized=USA country= lat/lon=[coordonnée retirée],-117.92529: geocode_provider is missing although coordinates are present

## Tiers fournisseurs

Les tiers ne forment pas une chaine multi-niveaux robuste. Apres les 15 premiers records, `first_transformation` et `raw_material` sont presque toujours vides; quand ils existent, plusieurs fournisseurs sont copies dans plusieurs tiers.

### SAME_SUPPLIER_ASSIGNED_TO_MULTIPLE_TIERS
- R1; Ens. Equipements latéraux / A5086 - Aluminium; supplier=FRN-BD805D8D4EB65E; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: supplier 'FRN-BD805D8D4EB65E' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[6] loc='France'
- R2; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium); supplier=FRN-BD805D8D4EB65E; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: supplier 'FRN-BD805D8D4EB65E' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[5] loc='France'
- R3; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=FRN-0B3DAD918C8F64; loc=Delaware - USA normalized=USA country= lat/lon=[coordonnée retirée],7.190275: supplier 'FRN-0B3DAD918C8F64' appears in multiple tiers: first_transformation[3] loc='Delaware - USA'; raw_material[3] loc='USA'
- R8; Ens. Stowage latéral / cuir; supplier=FRN-E857FD00FA3A46; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: supplier 'FRN-E857FD00FA3A46' appears in multiple tiers: first_transformation[1] loc='France'; raw_material[1] loc='France'
- R8; Ens. Stowage latéral / cuir; supplier=FRN-935B8529CE61B4; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.3633735: supplier 'FRN-935B8529CE61B4' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[2] loc='France'
- R8; Ens. Stowage latéral / cuir; supplier=FRN-727BE76F9CE12D; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: supplier 'FRN-727BE76F9CE12D' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[3] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=FRN-1BDCFA9C2C8341; loc=USA normalized=USA country= lat/lon=[coordonnée retirée],-75.1951162: supplier 'FRN-1BDCFA9C2C8341' appears in multiple tiers: first_transformation[1] loc='USA'; raw_material[1] loc='USA'
- R12; Stowage assemblé avec porte / Silicone; supplier=FRN-77A20D424743A6; loc=France normalized=France country= lat/lon=[coordonnée retirée],3.3759: supplier 'FRN-77A20D424743A6' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[2] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=FRN-DA7F97DC1B47FC; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.8154646: supplier 'FRN-DA7F97DC1B47FC' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[3] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=FRN-1E191B6E8030DB; loc=Japon normalized=Japan country= lat/lon=[coordonnée retirée],138.2529: supplier 'toschiba shinetsu' appears in multiple tiers: first_transformation[4] loc='Japon'; raw_material[4] loc='Japon'
- R12; Stowage assemblé avec porte / Silicone; supplier=FRN-8694A96AFD62DA; loc=Angleterre normalized=United Kingdom country= lat/lon=[coordonnée retirée],-3.436: supplier 'FRN-8694A96AFD62DA' appears in multiple tiers: first_transformation[5] loc='Angleterre'; raw_material[5] loc='Angleterre'
- R15; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL; supplier=FRN-C3B826345B6812; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: supplier 'FRN-C3B826345B6812' appears in multiple tiers: first_transformation[1] loc='France'; raw_material[14] loc='France'

### DUPLICATE_SUPPLIER_SAME_TIER
- R189 tier1[2,9]; Manchette acc. Mobile / Transport; supplier=FRN-297CE635156764; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: duplicate supplier ('FRN-297CE635156764 france', 'France') at positions ['2', '9']
- R189 tier1[3,10]; Manchette acc. Mobile / Transport; supplier=FRN-FCB0C890EFA2B8; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2372016: duplicate supplier ('FRN-FCB0C890EFA2B8 france', 'France') at positions ['3', '10']
- R189 tier1[4,11]; Manchette acc. Mobile / Transport; supplier=FRN-67CD5F21738C93; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: duplicate supplier ('FRN-67CD5F21738C93 france', 'France') at positions ['4', '11']
- R189 tier1[5,8]; Manchette acc. Mobile / Transport; supplier=FRN-54423E8FD293B7; loc=Angleterre normalized=United Kingdom country= lat/lon=[coordonnée retirée],-0.966526: duplicate supplier ('FRN-54423E8FD293B7 angleterre', 'United Kingdom') at positions ['5', '8']
- R189 tier1[6,12]; Manchette acc. Mobile / Transport; supplier=FRN-72A8D622F0F88D; loc=France normalized=France country= lat/lon=[coordonnée retirée],5.9552398: duplicate supplier ('ach france', 'France') at positions ['6', '12']
- R191 tier1[3,10]; Manchette équipée / Transport; supplier=FRN-FCB0C890EFA2B8; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2372016: duplicate supplier ('FRN-FCB0C890EFA2B8 france', 'France') at positions ['3', '10']
- R191 tier1[4,6,11]; Manchette équipée / Transport; supplier=FRN-72A8D622F0F88D; loc=France normalized=France country= lat/lon=[coordonnée retirée],5.9552398: duplicate supplier ('ach france', 'France') at positions ['4', '6', '11']
- R211 tier1[1,3]; Support écran / Transport; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: duplicate supplier ('FRN-F1F796DB13C8E2 france', 'France') at positions ['1', '3']
- R237 tier1[2,5]; Siége / aluminium; supplier=FRN-9B72BBB9F69F3D; loc=Japon normalized=Japan country=Japan lat/lon=[coordonnée retirée],138.2529: duplicate supplier ('FRN-9B72BBB9F69F3D japon', 'Japan') at positions ['2', '5']
- R238 tier1[2,5]; Siége / Tissu, mousse, polyéthylène; supplier=FRN-72A8D622F0F88D; loc=France normalized=France country= lat/lon=[coordonnée retirée],5.9552398: duplicate supplier ('ach france', 'France') at positions ['2', '5']
- R239 tier1[2,5,8]; Siége / Moulage plastique; supplier=FRN-4AAE68951598B8; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: duplicate supplier ('baule exsto polymere france', 'France') at positions ['2', '5', '8']
- R240 tier1[2,6]; Siége / autre (silicium, cuirs synthétique); supplier=FRN-72A8D622F0F88D; loc=France normalized=France country= lat/lon=[coordonnée retirée],5.9552398: duplicate supplier ('ach france', 'France') at positions ['2', '6']

### TIER1_SELF_OR_CUSTOMER_AS_SUPPLIER
- R44 tier1[1]; Support écran / A5086 - Aluminium; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R67 tier1[1]; Support écran / acier; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R77 tier1[2]; SFCU (Seat Function Control Unit) / Clavier; supplier=FRN-25A8C56CB9C639; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R78 tier1[1]; Commande actionnement ECU / Commande actionnement ECU; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R82 tier1[1]; Ecran - Screen Display (COTS) / Display, liquid crystal, 17 pouces; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R108 tier1[1]; Support écran / inox; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R131 tier1[1]; Ecran - 00-5136-51 Rev F Seat Power Box 4 (SPB4) / Display, liquid crystal, 17 pouces; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R133 tier1[1]; Commande actionnement ECU / packaging; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R134 tier1[1]; Commande actionnement ECU / Transport; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R139 tier1[1]; Ecran / packaging; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R140 tier1[1]; Ecran / Transport; supplier=FRN-F1F796DB13C8E2; loc=France normalized=France country= lat/lon=[coordonnée retirée],4.42273: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R170 tier1[2]; Powerbox / powerbox; supplier=FRN-F1F796DB13C8E2; loc=USA normalized=USA country= lat/lon=[coordonnée retirée],-100.4458825: FRN-F1F796DB13C8E2 appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier

## Qualite des noms et composants

### SUPPLIER_NAME_MALFORMED
- R1 tier1[1]; Ens. Equipements latéraux / A5086 - Aluminium; supplier=FRN-45A091671294B0; loc=France normalized=France country= lat/lon=[coordonnée retirée],-0.6475364: name issues: asterisk_marker
- R1 raw_material[2]; Ens. Equipements latéraux / A5086 - Aluminium; supplier=FRN-798BE9ED657B85; loc=France normalized=France country= lat/lon=[coordonnée retirée],5.607597: name issues: unbalanced_parentheses
- R2 first_transformation[3]; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium); supplier=FRN-83186B5AEF84D8; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.8415731: name issues: asterisk_marker
- R3 tier1[1]; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=FRN-45A091671294B0; loc=France normalized=France country= lat/lon=[coordonnée retirée],-0.6475364: name issues: asterisk_marker
- R4 tier1[1]; Accoudoir allée / packaging; supplier=FRN-72A106312E8F95; loc=France normalized=France country= lat/lon=[coordonnée retirée],1.2085766: name issues: asterisk_marker
- R5 tier1[1]; Accoudoir allée / Transport; supplier=FRN-72A106312E8F95; loc=France normalized=France country= lat/lon=[coordonnée retirée],1.2085766: name issues: asterisk_marker
- R6 tier1[1]; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2; supplier=FRN-2229587D79B6E7; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: name issues: unbalanced_parentheses
- R8 tier1[1]; Ens. Stowage latéral / cuir; supplier=FRN-2229587D79B6E7; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.2137: name issues: unbalanced_parentheses
- R9 tier1[1]; Brackets set / Transport; supplier=FRN-E8268BC81624C2; loc=USA normalized=USA country= lat/lon=[coordonnée retirée],-100.4458825: name issues: asterisk_marker
- R10 tier1[1]; lightning / lightning; supplier=FRN-58617EE9251D1E; loc=France normalized=France country= lat/lon=[coordonnée retirée],2.4021145: name issues: asterisk_marker

### COMPONENT_IS_NOT_A_MATERIAL_OR_PART
- R4; Accoudoir allée / packaging: component is a logistics/package placeholder rather than a material or part
- R5; Accoudoir allée / Transport: component is a logistics/package placeholder rather than a material or part
- R9; Brackets set / Transport: component is a logistics/package placeholder rather than a material or part
- R90; Brackets set / packaging: component is a logistics/package placeholder rather than a material or part
- R103; Bumper version porte / packaging: component is a logistics/package placeholder rather than a material or part
- R122; Bumper version porte / Transport: component is a logistics/package placeholder rather than a material or part
- R128; Capot NFC / packaging: component is a logistics/package placeholder rather than a material or part
- R129; Capot NFC / Transport: component is a logistics/package placeholder rather than a material or part
- R130; Ceinture de sécurité / packaging: component is a logistics/package placeholder rather than a material or part
- R132; Ceinture de sécurité / Transport: component is a logistics/package placeholder rather than a material or part

### EMPTY_SYSTEM_OR_COMPONENT
- R16: system and/or component is empty

## Transport

`from_supplier_to_FRN-F1F796DB13C8E2` est presque toujours renseigne, mais avec des listes melangeant modes simples et chaines composites. `to_first_transformation` et `mine_to_refinery` sont majoritairement vides, donc les amonts matiere ne sont pas modelises de maniere exploitable.

### TRANSPORT_MODES_EMPTY
- R1; Ens. Equipements latéraux / A5086 - Aluminium: mine_to_refinery.modes is empty or missing
- R2; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium): mine_to_refinery.modes is empty or missing
- R4; Accoudoir allée / packaging: mine_to_refinery.modes is empty or missing
- R5; Accoudoir allée / Transport: mine_to_refinery.modes is empty or missing
- R7; Bumper version porte / alliage Cu: mine_to_refinery.modes is empty or missing
- R8; Ens. Stowage latéral / cuir: mine_to_refinery.modes is empty or missing
- R9; Brackets set / Transport: mine_to_refinery.modes is empty or missing
- R11; Padding (rembourrage) / AIRVOLT LAMINAT: mine_to_refinery.modes is empty or missing
- R14; Coussin ottoman / tissu: mine_to_refinery.modes is empty or missing
- R15; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL: mine_to_refinery.modes is empty or missing

### TRANSPORT_MODE_NOT_A_TRANSPORT_MODE
- R6; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: to_first_transformation.modes contains non-mode value: Bilogistik SA
- R6; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: mine_to_refinery.modes contains non-mode value: Caoutchouc naturel --> Bateau
- R6; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: mine_to_refinery.modes contains non-mode value: Caoutchouc synthétique (résine) --> Bateau - Camion
- R8; Ens. Stowage latéral / cuir: to_first_transformation.modes contains non-mode value: Interne entreprise
- R247; nan / nan: from_supplier_to_FRN-F1F796DB13C8E2.modes contains non-mode value: nan

### TRANSPORT_MODE_COMBINED_OR_UNNORMALIZED
- R6; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: mine_to_refinery.modes mixes combined route strings with a mode list: Caoutchouc synthétique (résine) --> Bateau - Camion
- R75; Brackets set / cables FJKL1-3K1J01-01ATAB_BRACKETS-SET: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R76; Ens. Structure fauteuil / acier: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R90; Brackets set / packaging: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R102; Ens. Structure fauteuil / GLO: moulage par injection plastique: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R109; Capot NFC / kydex: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R110; Coussin ottoman / kydex: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R111; Ens. Stowage latéral / kydex: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R112; Ensemble porte / kydex: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau
- R113; Ens. Tablette cocktail / kydex: from_supplier_to_FRN-F1F796DB13C8E2.modes mixes combined route strings with a mode list: Camion - Bateau

## Priorites de correction

1. Recharger les masses et parts de marche avant tout calcul d impact ou agregation.
2. Clarifier le modele de tiers: Tier 1 = fournisseur direct de la piece/sous-ensemble; first_transformation = transformateur matiere; raw_material = producteur/extracteur matiere. Ne pas copier le meme fournisseur dans plusieurs tiers sans justification.
3. Normaliser `location` en pays ISO ou champ structure (`country`, `region`, `city`, `site_name`) et supprimer les valeurs `s`, vide, `FRN-4F3EF5C6442315`, `Montreal`, `Californie - USA`, `Delaware - USA`.
4. Re-geocoder uniquement avec des adresses de sites industriels verifiees; marquer separement les centroides pays comme fallback, pas comme coordonnees fournisseur.
5. Separer les records de pieces/matieres des records `Transport` et `packaging`, car ils ne representent pas le meme objet de supply.
6. Normaliser les modes transport en valeurs atomiques (`truck`, `ship`, `rail`, `air`) et garder les combinaisons dans une structure de route/leg separee.
