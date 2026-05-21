# Audit output8_GEO.json

Source: `data/output8_GEO.json`
Records: 247
Supplier entries: 1118
Detailed findings: `data/output8_GEO_audit_findings.csv`

## Bilan court

Le JSON n est pas fiable tel quel pour un modele de supply chain de siege aeronautique: les donnees de masse et de parts de marche sont vides, la profondeur Tier est presque toujours absente apres Tier 1, et les localisations ne sont pas homogenes. Les erreurs les plus critiques sont les contradictions entre `location`, `country`, `lat/lon` et `geocode_query`, notamment sur Jamco, Lauak, MGR Foamtex, Plastiservice, J&C Aero et plusieurs entrees Airbus Atlantique/STELIA.

## Chiffres cles

- Constats generes: 3157 au total: HIGH=428, MEDIUM=2150, LOW=579.
- Entrees fournisseurs par tier: tier1=957, first_transformation=73, raw_material=88. `primary_material` est vide partout.
- Couverture tier: `tier1` vide pour 2 records; `first_transformation` vide pour 232/247; `raw_material` vide pour 232/247; `primary_material` vide pour 247/247.
- Geocodage: cache:nominatim=656, country_centroid=439, nominatim=20, (missing)=3. Le fichier contient 595 coordonnees detectees comme centroides de pays ou equivalentes.
- Donnees quantitatives: `mass_kg=0.0` sur 247/247 records; `market_share_pct=""` sur 247/247 records.
- Libelles de localisation les plus frequents: 'France'=789, 'USA'=55, 'Pologne'=55, 'Belgique'=42, 'Allemagne'=33, 'Thailande'=25, 'Japon'=23, 'Angleterre'=22, 's'=9, 'Inde'=8, 'Chine'=8, 'Thailand'=8, 'Airbus Atlantique'=8, ''=5, 'Lituanie'=4, 'Californie - USA'=3, 'Autriche'=2, 'Luxembourg'=2.

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
- R39 tier1[4]; Manchette acc. Mobile / A5086 - Aluminium; supplier=Figeac Aéro (France) (s); loc=s normalized=INVALID_S country= lat/lon=44.590773,2.0333182: location is not a usable country/location: 's'
- R40 tier1[4]; Manchette équipée / A5086 - Aluminium; supplier=Figeac Aéro (France) (s); loc=s normalized=INVALID_S country= lat/lon=44.590773,2.0333182: location is not a usable country/location: 's'
- R63 tier1[4]; Manchette équipée / acier; supplier=Lauak Group (France) (s); loc=s normalized=INVALID_S country=France lat/lon=46.2276,2.2137: location is not a usable country/location: 's'
- R74 tier1[4]; Manchette acc. Mobile / Alu; supplier=Figeac Aéro (France) (s); loc=s normalized=INVALID_S country= lat/lon=44.590773,2.0333182: location is not a usable country/location: 's'
- R147 tier1[5]; Ens. Equipements latéraux / packaging; supplier=Celso (France) (s); loc=s normalized=INVALID_S country= lat/lon=-27.317161,-48.557608: location is not a usable country/location: 's'
- R148 tier1[5]; Ens. Equipements latéraux / Transport; supplier=Celso (France) (s); loc=s normalized=INVALID_S country= lat/lon=-27.317161,-48.557608: location is not a usable country/location: 's'
- R189 tier1[7]; Manchette acc. Mobile / Transport; supplier=Lauak Group (France) (s); loc=s normalized=INVALID_S country=France lat/lon=46.2276,2.2137: location is not a usable country/location: 's'
- R190 tier1[7]; Manchette acc. Mobile / packaging; supplier=Lauak Group (France) (s); loc=s normalized=INVALID_S country=France lat/lon=46.2276,2.2137: location is not a usable country/location: 's'
- R191 tier1[5]; Manchette équipée / Transport; supplier=MGR FOAMTEX (Angleterre) (s); loc=s normalized=INVALID_S country= lat/lon=51.739561,-0.966526: location is not a usable country/location: 's'
- R219 tier1[1]; Manchette équipée / velcro; supplier=ACH; loc= normalized=INVALID_EMPTY country= lat/lon=38.7560499,-8.9608437: location is not a usable country/location: ''

### COUNTRY_FIELD_LOCATION_MISMATCH
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'
- R63 tier1[4]; Manchette équipée / acier; supplier=Lauak Group (France) (s); loc=s normalized=INVALID_S country=France lat/lon=46.2276,2.2137: country='France' conflicts with location='s'
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=Lauak Group (France) (Thailande); loc=Thailande normalized=Thailand country=France lat/lon=46.2276,2.2137: country='France' conflicts with location='Thailande'
- R85 tier1[3]; Ens. Structure fauteuil / inox; supplier=Lauak Group (France) (Thailand); loc=Thailand normalized=Thailand country=France lat/lon=46.2276,2.2137: country='France' conflicts with location='Thailand'
- R87 tier1[5]; Ens. Tablette repas / Ertalon; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: country='Japan' conflicts with location='France'

### GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=Lauak Group (France) (Thailande); loc=Thailande normalized=Thailand country=France lat/lon=46.2276,2.2137: geocode_query countries=['France'] do not include normalized location=Thailand
- R80 tier1[3]; Manchette acc. Mobile / cuir; supplier=MGR FOAMTEX (Angleterre) (France); loc=France normalized=France country= lat/lon=51.739561,-0.966526: geocode_query countries=['United Kingdom'] do not include normalized location=France
- R85 tier1[3]; Ens. Structure fauteuil / inox; supplier=Lauak Group (France) (Thailand); loc=Thailand normalized=Thailand country=France lat/lon=46.2276,2.2137: geocode_query countries=['France'] do not include normalized location=Thailand
- R87 tier1[5]; Ens. Tablette repas / Ertalon; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: geocode_query countries=['Japan'] do not include normalized location=France

### COORDINATE_OUTSIDE_LOCATION_COUNTRY
- R3 first_transformation[3]; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=DuPont de Nemours; loc=Delaware - USA normalized=USA country= lat/lon=47.7979001,7.190275: lat/lon (47.7979001,7.190275) are outside normalized location country USA
- R11 raw_material[5]; Padding (rembourrage) / AIRVOLT LAMINAT; supplier=Nordic Paper Oyj; loc=Finlande normalized=Finland country= lat/lon=59.1400084,12.9178462: lat/lon (59.1400084,12.9178462) are outside normalized location country Finland
- R24 tier1[6]; Ens. Tablette cocktail / A2017 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R25 tier1[4]; Ens. Tablette repas / A2017 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R30 tier1[5]; Ens. Tablette cocktail / A2024 - Aluminium; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R31 tier1[4]; Ens. Tablette repas / A2024 - Aluminium; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R49 tier1[3]; Ceinture de sécurité / acier; supplier=J&C Aero (Lituanie); loc=Lituanie normalized=Lithuania country= lat/lon=-20.5228026,-54.6480379: lat/lon (-20.5228026,-54.6480379) are outside normalized location country Lithuania
- R60 tier1[5]; Ens. Tablette cocktail / acier; supplier=Jamco Corp (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R61 tier1[4]; Ens. Tablette repas / acier; supplier=Jamco (Japon) (France); loc=France normalized=France country=Japan lat/lon=36.2048,138.2529: lat/lon (36.2048,138.2529) are outside normalized location country France
- R76 tier1[3]; Ens. Structure fauteuil / acier; supplier=Lauak Group (France) (Thailande); loc=Thailande normalized=Thailand country=France lat/lon=46.2276,2.2137: lat/lon (46.2276,2.2137) are outside normalized location country Thailand

### GEOCODE_PROVIDER_MISSING
- R50 tier1[2]; Support clamps / acier; supplier=Ancra Aircraft (Californie - USA); loc=Californie - USA normalized=USA country= lat/lon=34.11167,-117.92529: geocode_provider is missing although coordinates are present
- R191 tier1[5]; Manchette équipée / Transport; supplier=MGR FOAMTEX (Angleterre) (s); loc=s normalized=INVALID_S country= lat/lon=51.739561,-0.966526: geocode_provider is missing although coordinates are present
- R209 tier1[3]; Support clamps / packaging; supplier=Ancra Aircraft (Californie - USA); loc=Californie - USA normalized=USA country= lat/lon=34.11167,-117.92529: geocode_provider is missing although coordinates are present

## Tiers fournisseurs

Les tiers ne forment pas une chaine multi-niveaux robuste. Apres les 15 premiers records, `first_transformation` et `raw_material` sont presque toujours vides; quand ils existent, plusieurs fournisseurs sont copies dans plusieurs tiers.

### SAME_SUPPLIER_ASSIGNED_TO_MULTIPLE_TIERS
- R1; Ens. Equipements latéraux / A5086 - Aluminium; supplier=Thyssen group; loc=France normalized=France country= lat/lon=46.2276,2.2137: supplier 'thyssen group' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[6] loc='France'
- R2; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium); supplier=Thyssen group; loc=France normalized=France country= lat/lon=46.2276,2.2137: supplier 'thyssen group' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[5] loc='France'
- R3; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=DuPont de Nemours; loc=Delaware - USA normalized=USA country= lat/lon=47.7979001,7.190275: supplier 'dupont de nemours' appears in multiple tiers: first_transformation[3] loc='Delaware - USA'; raw_material[3] loc='USA'
- R8; Ens. Stowage latéral / cuir; supplier=La Filière Française du cuir; loc=France normalized=France country= lat/lon=46.2276,2.2137: supplier 'la filiere francaise du cuir' appears in multiple tiers: first_transformation[1] loc='France'; raw_material[1] loc='France'
- R8; Ens. Stowage latéral / cuir; supplier=Maison Fichet; loc=France normalized=France country= lat/lon=48.8706283,2.3633735: supplier 'maison fichet' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[2] loc='France'
- R8; Ens. Stowage latéral / cuir; supplier=EUREKA SARL DERAYGE SERVICE; loc=France normalized=France country= lat/lon=46.2276,2.2137: supplier 'eureka sarl derayge service' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[3] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=Général Electric; loc=USA normalized=USA country= lat/lon=41.0195211,-75.1951162: supplier 'general electric' appears in multiple tiers: first_transformation[1] loc='USA'; raw_material[1] loc='USA'
- R12; Stowage assemblé avec porte / Silicone; supplier=Saint Gobain; loc=France normalized=France country= lat/lon=49.5967,3.3759: supplier 'saint gobain' appears in multiple tiers: first_transformation[2] loc='France'; raw_material[2] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=Rhône Poulenc; loc=France normalized=France country= lat/lon=50.2986,2.8154646: supplier 'rhone poulenc' appears in multiple tiers: first_transformation[3] loc='France'; raw_material[3] loc='France'
- R12; Stowage assemblé avec porte / Silicone; supplier=Toschiba-Shinetsu; loc=Japon normalized=Japan country= lat/lon=36.2048,138.2529: supplier 'toschiba shinetsu' appears in multiple tiers: first_transformation[4] loc='Japon'; raw_material[4] loc='Japon'
- R12; Stowage assemblé avec porte / Silicone; supplier=Silicon Engineering; loc=Angleterre normalized=United Kingdom country= lat/lon=55.3781,-3.436: supplier 'silicon engineering' appears in multiple tiers: first_transformation[5] loc='Angleterre'; raw_material[5] loc='Angleterre'
- R15; Manchette acc. Mobile / FRMC55:EU28 polyuréthane flexible traité UL; supplier=Euralliage; loc=France normalized=France country= lat/lon=46.2276,2.2137: supplier 'euralliage' appears in multiple tiers: first_transformation[1] loc='France'; raw_material[14] loc='France'

### DUPLICATE_SUPPLIER_SAME_TIER
- R189 tier1[2,9]; Manchette acc. Mobile / Transport; supplier=segnere aero SAS (France); loc=France normalized=France country= lat/lon=46.2276,2.2137: duplicate supplier ('segnere aero sas france', 'France') at positions ['2', '9']
- R189 tier1[3,10]; Manchette acc. Mobile / Transport; supplier=GATTEFIN (France); loc=France normalized=France country= lat/lon=47.1426393,2.2372016: duplicate supplier ('gattefin france', 'France') at positions ['3', '10']
- R189 tier1[4,11]; Manchette acc. Mobile / Transport; supplier=Celso (France); loc=France normalized=France country= lat/lon=46.2276,2.2137: duplicate supplier ('celso france', 'France') at positions ['4', '11']
- R189 tier1[5,8]; Manchette acc. Mobile / Transport; supplier=MGR FOAMTEX (Angleterre); loc=Angleterre normalized=United Kingdom country= lat/lon=51.739561,-0.966526: duplicate supplier ('mgr foamtex angleterre', 'United Kingdom') at positions ['5', '8']
- R189 tier1[6,12]; Manchette acc. Mobile / Transport; supplier=ACH (France); loc=France normalized=France country= lat/lon=45.6912098,5.9552398: duplicate supplier ('ach france', 'France') at positions ['6', '12']
- R191 tier1[3,10]; Manchette équipée / Transport; supplier=GATTEFIN (France); loc=France normalized=France country= lat/lon=47.1426393,2.2372016: duplicate supplier ('gattefin france', 'France') at positions ['3', '10']
- R191 tier1[4,6,11]; Manchette équipée / Transport; supplier=ACH (France); loc=France normalized=France country= lat/lon=45.6912098,5.9552398: duplicate supplier ('ach france', 'France') at positions ['4', '6', '11']
- R211 tier1[1,3]; Support écran / Transport; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: duplicate supplier ('safran france', 'France') at positions ['1', '3']
- R237 tier1[2,5]; Siége / aluminium; supplier=Jamco corp (Japon); loc=Japon normalized=Japan country=Japan lat/lon=36.2048,138.2529: duplicate supplier ('jamco corp japon', 'Japan') at positions ['2', '5']
- R238 tier1[2,5]; Siége / Tissu, mousse, polyéthylène; supplier=ACH (France); loc=France normalized=France country= lat/lon=45.6912098,5.9552398: duplicate supplier ('ach france', 'France') at positions ['2', '5']
- R239 tier1[2,5,8]; Siége / Moulage plastique; supplier=Baulé- Exsto Polymère (France); loc=France normalized=France country= lat/lon=46.2276,2.2137: duplicate supplier ('baule exsto polymere france', 'France') at positions ['2', '5', '8']
- R240 tier1[2,6]; Siége / autre (silicium, cuirs synthétique); supplier=ACH (France); loc=France normalized=France country= lat/lon=45.6912098,5.9552398: duplicate supplier ('ach france', 'France') at positions ['2', '6']

### TIER1_SELF_OR_CUSTOMER_AS_SUPPLIER
- R44 tier1[1]; Support écran / A5086 - Aluminium; supplier=SAFRAN(France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R67 tier1[1]; Support écran / acier; supplier=SAFRAN(France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R77 tier1[2]; SFCU (Seat Function Control Unit) / Clavier; supplier=SAFRAN - Filiale SeatNet (France); loc=France normalized=France country= lat/lon=46.2276,2.2137: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R78 tier1[1]; Commande actionnement ECU / Commande actionnement ECU; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R82 tier1[1]; Ecran - Screen Display (COTS) / Display, liquid crystal, 17 pouces; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R108 tier1[1]; Support écran / inox; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R131 tier1[1]; Ecran - 00-5136-51 Rev F Seat Power Box 4 (SPB4) / Display, liquid crystal, 17 pouces; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R133 tier1[1]; Commande actionnement ECU / packaging; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R134 tier1[1]; Commande actionnement ECU / Transport; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R139 tier1[1]; Ecran / packaging; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R140 tier1[1]; Ecran / Transport; supplier=SAFRAN (France); loc=France normalized=France country= lat/lon=46.8092197,4.42273: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier
- R170 tier1[2]; Powerbox / powerbox; supplier=SAFRAN (France) (USA); loc=USA normalized=USA country= lat/lon=39.7837304,-100.4458825: Safran appears as tier1 supplier; check whether this is internal flow or customer wrongly listed as supplier

## Qualite des noms et composants

### SUPPLIER_NAME_MALFORMED
- R1 tier1[1]; Ens. Equipements latéraux / A5086 - Aluminium; supplier=ESPACE (France)*; loc=France normalized=France country= lat/lon=44.7776436,-0.6475364: name issues: asterisk_marker
- R1 raw_material[2]; Ens. Equipements latéraux / A5086 - Aluminium; supplier=Constellium (France; loc=France normalized=France country= lat/lon=45.3094248,5.607597: name issues: unbalanced_parentheses
- R2 first_transformation[3]; Ens. Stowage latéral / 15CDV6 (chrome, molibdene, vanadium); supplier=Aubert&Duval (France)*; loc=France normalized=France country= lat/lon=45.9235016,2.8415731: name issues: asterisk_marker
- R3 tier1[1]; Ens. Equipements latéraux / Ertalon par moulage par injection plastique; supplier=ESPACE (France)*; loc=France normalized=France country= lat/lon=44.7776436,-0.6475364: name issues: asterisk_marker
- R4 tier1[1]; Accoudoir allée / packaging; supplier=SUMPAR (France)*; loc=France normalized=France country= lat/lon=49.3892868,1.2085766: name issues: asterisk_marker
- R5 tier1[1]; Accoudoir allée / Transport; supplier=SUMPAR (France)*; loc=France normalized=France country= lat/lon=49.3892868,1.2085766: name issues: asterisk_marker
- R6 tier1[1]; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2; supplier=MGA (Villeneuve St Lot; loc=France normalized=France country= lat/lon=46.2276,2.2137: name issues: unbalanced_parentheses
- R8 tier1[1]; Ens. Stowage latéral / cuir; supplier=MGA (Villeneuve St Lot; loc=France normalized=France country= lat/lon=46.2276,2.2137: name issues: unbalanced_parentheses
- R9 tier1[1]; Brackets set / Transport; supplier=JAMMY Inc (USA)*; loc=USA normalized=USA country= lat/lon=39.7837304,-100.4458825: name issues: asterisk_marker
- R10 tier1[1]; lightning / lightning; supplier=S.E.L.A (France)*; loc=France normalized=France country= lat/lon=48.8012986,2.4021145: name issues: asterisk_marker

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

`from_supplier_to_safran` est presque toujours renseigne, mais avec des listes melangeant modes simples et chaines composites. `to_first_transformation` et `mine_to_refinery` sont majoritairement vides, donc les amonts matiere ne sont pas modelises de maniere exploitable.

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
- R247; nan / nan: from_supplier_to_safran.modes contains non-mode value: nan

### TRANSPORT_MODE_COMBINED_OR_UNNORMALIZED
- R6; Ensemble porte / FILM DECOR AERFILM - Ep0.33 714g-m2: mine_to_refinery.modes mixes combined route strings with a mode list: Caoutchouc synthétique (résine) --> Bateau - Camion
- R75; Brackets set / cables FJKL1-3K1J01-01ATAB_BRACKETS-SET: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R76; Ens. Structure fauteuil / acier: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R90; Brackets set / packaging: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R102; Ens. Structure fauteuil / GLO: moulage par injection plastique: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R109; Capot NFC / kydex: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R110; Coussin ottoman / kydex: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R111; Ens. Stowage latéral / kydex: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R112; Ensemble porte / kydex: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau
- R113; Ens. Tablette cocktail / kydex: from_supplier_to_safran.modes mixes combined route strings with a mode list: Camion - Bateau

## Priorites de correction

1. Recharger les masses et parts de marche avant tout calcul d impact ou agregation.
2. Clarifier le modele de tiers: Tier 1 = fournisseur direct de la piece/sous-ensemble; first_transformation = transformateur matiere; raw_material = producteur/extracteur matiere. Ne pas copier le meme fournisseur dans plusieurs tiers sans justification.
3. Normaliser `location` en pays ISO ou champ structure (`country`, `region`, `city`, `site_name`) et supprimer les valeurs `s`, vide, `Airbus Atlantique`, `Montreal`, `Californie - USA`, `Delaware - USA`.
4. Re-geocoder uniquement avec des adresses de sites industriels verifiees; marquer separement les centroides pays comme fallback, pas comme coordonnees fournisseur.
5. Separer les records de pieces/matieres des records `Transport` et `packaging`, car ils ne representent pas le meme objet de supply.
6. Normaliser les modes transport en valeurs atomiques (`truck`, `ship`, `rail`, `air`) et garder les combinaisons dans une structure de route/leg separee.
