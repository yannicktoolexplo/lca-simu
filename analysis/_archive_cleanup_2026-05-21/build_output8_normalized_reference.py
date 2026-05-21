import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path


AUDIT = Path("analysis/output8_GEO_normalized_audit_findings.csv")
OUT_CORR = Path("analysis/output8_GEO_normalized_reference_corrections.csv")
OUT_SRC = Path("analysis/output8_GEO_normalized_reference_sources.csv")
OUT_MD = Path("analysis/output8_GEO_normalized_reference_corrections.md")


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def row(source_id, entity, source_type, url, evidence, country, address, role, confidence):
    return {
        "source_id": source_id,
        "entity": entity,
        "source_type": source_type,
        "url": url,
        "evidence": evidence,
        "canonical_country": country,
        "canonical_site_address": address,
        "canonical_role": role,
        "confidence": confidence,
    }


sources = [
    row("SRC_JAMCO_001", "JAMCO Aircraft Interiors / JAMCO Philippines", "official_company", "https://www.jamco.co.jp/en/company/group.html", "JAMCO group page lists Niigata, Miyazaki and Philippines aircraft-interiors sites.", "Japan / Philippines depending site", "Niigata: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822; Miyazaki: 8136-7 Tanocho-ko, Miyazaki 889-1701; Philippines: N7000 Gil Puyat Avenue, Clark Civil Aviation Complex, Pampanga.", "tier1 aircraft interiors manufacturer", "high"),
    row("SRC_MGR_001", "MGR Foamtex Ltd", "official_company", "https://www.mgrfoamtex.com/contact-us", "Contact page gives DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK.", "United Kingdom", "DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK", "aircraft upholstery / foam systems supplier", "high"),
    row("SRC_LAUAK_001", "Groupe LAUAK", "official_company", "https://www.groupe-lauak.com/lauak-groupe/presentation-du-groupe/sites/", "LAUAK sites page lists Hasparren and other group sites.", "France, plus other group countries depending site", "2245 Route de Minhotz, 64240 Hasparren, France", "aerostructures / sheet metal / machining / structural assembly supplier", "medium_high"),
    row("SRC_PLASTISERVICE_001", "Plastiservice Charleroi", "official_company", "https://plastiservice.com/nos-implantations/", "Locations page lists Plastiservice Charleroi at ZI de Jumet, Allee Centrale 72, B-6040 Charleroi.", "Belgium", "ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium", "tier2 plastics materials / processing supplier", "high"),
    row("SRC_JCAERO_001", "J&C Aero", "official_company", "https://e.jcaero.com/contactus", "Contact page lists Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279.", "Lithuania", "Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279", "tier1 aircraft interior provider", "high"),
    row("SRC_STELIA_AIRBUS_001", "STELIA Aerospace / Airbus Atlantic", "official_group", "https://www.airbus.com/fr/products-services/commercial-aircraft/airframes/airbus-atlantic/amenagement-cabine", "Airbus identifies STELIA Aerospace as Airbus Atlantic premium passenger seat brand.", "France", "Rochefort, France when no better site is proven", "premium passenger seat brand / Airbus Atlantic cabin interiors", "medium_high"),
    row("SRC_SAFRAN_SEATS_001", "Safran Seats", "official_group", "https://www.safran-group.com/locations", "Safran locations list Safran Seats sites including Plaisir, Issoudun, Saint-Crepin-Ibouvillers and Gainesville.", "France / USA / UK depending actual site", "Use actual Safran Seats site; HQ fallback: 61 Rue Pierre Curie, 78373 Plaisir, France", "OEM/internal final integrator in this dataset context", "high"),
    row("SRC_FIGEAC_001", "Figeac Aero", "official_company", "https://www.figeac-aero.com/fr/contact", "Contact page lists Zone industrielle de l Aiguille, 46100 Figeac, France.", "France", "Zone industrielle de l'Aiguille, 46100 Figeac, France", "tier1 aerostructures / assemblies supplier", "high"),
    row("SRC_GATTEFIN_001", "ETS Gattefin", "official_company", "https://gattefin.fr/", "Official site gives 201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre and aerospace activity.", "France", "201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France", "tier1 precision machining supplier", "high"),
    row("SRC_SEGNERE_001", "Groupe Segnere / SEGNERE Ade", "industry_association", "https://www.space-aero.org/en/member/segnere-ade/", "SPACE Aero member page lists SEGNERE Ade in France with precision mechanics, sheet metal and structural assembly.", "France", "Z.I. du Toulicou, Ade, Occitanie 65100, France", "tier1 precision mechanics / sheet metal / assembly supplier", "medium_high"),
    row("SRC_CELSO_001", "Celso SAS", "official_company", "https://celso.fr/en/contact-us/", "Contact page lists Celso SAS, 200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols.", "France", "200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France", "foam and cellular materials transformer", "high"),
    row("SRC_ACH_001", "ACH", "official_company", "https://www.ach-aeronefs.fr/en/contact/", "Contact page lists 16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers.", "France", "16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France", "aircraft upholstery / foams / seats supplier", "high"),
    row("SRC_EXSTO_001", "EXSTO / Baule-Exsto Polymere", "official_company", "https://www.exsto.com/en/contact", "EXSTO contact page gives headquarter at 55 avenue de la Deportation, 26100 Romans-sur-Isere.", "France", "55 avenue de la Deportation, 26100 Romans-sur-Isere, France", "technical polymer / polyurethane supplier", "high"),
    row("SRC_ANCRA_001", "Ancra International / Ancra Aircraft", "official_company", "https://ancraaircraft.com/about-us/", "Ancra Aircraft Division lists Ancra International, 601 S Vincent Ave, Azusa, CA 91702.", "USA", "601 S Vincent Ave, Azusa, CA 91702, USA", "tier1 cargo restraint / fittings / aircraft systems supplier", "high"),
    row("SRC_TA_001", "TA Aerospace", "official_company", "https://www.taaerospace.com/", "Official site describes aerospace clamping devices, thermal insulation products and engineered solutions.", "USA", "Valencia, California, USA - verify exact site address before geocoding", "tier1 aerospace clamps / insulation supplier", "medium"),
    row("SRC_E2IP_001", "e2ip technologies", "official_company", "https://e2ip.com/contact/", "Contact page lists Design & Manufacturing Center at 1455, 32nd Avenue, Lachine, QC H8T 3J1.", "Canada", "1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada", "tier2 electronics / HMI supplier", "high"),
    row("SRC_THYSSEN_001", "thyssenkrupp Materials France", "official_company", "https://www.thyssenkrupp-aerospace.com/en/company/locations/france", "France location page lists Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas and materials/supply-chain capabilities.", "France", "Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France", "tier3 material distributor / supply-chain service provider", "high"),
    row("SRC_EURALLIAGE_001", "Euralliage Ile de France", "official_company", "https://www.euralliage.com/coordonnees.htm", "Coordinates page lists 3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse.", "France", "3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France", "tier3 non-ferrous metals stockist/trader/cutting service", "high"),
    row("SRC_TATA_STEEL_001", "Tata Steel", "official_group", "https://www.tata.com/business/tata-steel", "Tata group page states Tata Steel operates in India in Jamshedpur, Gamharia, Kalinganagar and Meramandali.", "India", "Choose actual India plant from traceability", "tier4 steel producer / upstream material producer", "medium_high"),
    row("SRC_DUPONT_001", "DuPont de Nemours", "official_company", "https://www.dupont.com/locations.html.html", "DuPont locations page lists Wilmington, Delaware global headquarters and many global sites.", "USA unless a specific non-US manufacturing site is proven", "Choose product/site from DuPont locations and traceability", "tier2 chemical/material producer or transformer", "medium_high"),
    row("SRC_NORDIC_PAPER_001", "Nordic Paper", "official_company", "https://www.nordic-paper.com/en/contact", "Contact/about pages list mills in Sweden, Norway and Canada; not Finland.", "Sweden / Norway / Canada depending mill", "Choose actual mill: Saffle/Amotfors/Backhammar, Sweden; Greaker, Norway; Quebec, Canada", "specialty paper/pulp producer", "high"),
    row("SRC_SCHROTH_001", "SCHROTH Safety Products", "official_company", "https://www.schroth.com/en/contact/", "Contact page lists SCHROTH Safety Products GmbH in Arnsberg, Germany and SCHROTH Safety Products LLC in Fort Lauderdale, USA.", "Germany or USA depending actual site", "Germany: Arnsberg; USA: 5320 NW 35th Ave, Fort Lauderdale, FL 33309", "safety restraint products supplier", "high"),
    row("SRC_ANJOU_001", "Anjou Aeronautique", "official_company", "https://www.anjouaero.com/contact/", "Contact page lists 4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France.", "France", "4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France", "tier1 aeronautical interiors / manufacturing supplier", "high"),
    row("SRC_SENIOR_THAILAND_001", "Senior Aerospace Thailand", "official_company", "https://www.senior-thailand.com/Web/contact", "Contact page lists factories at 789/115-116 and 789/198 Moo 1, Nhongkham Sriracha, Chonburi.", "Thailand", "789/115-116 Moo 1, Nhongkham Sriracha, Chonburi 20230, Thailand", "tier1 high-precision aerospace systems / cabin interiors manufacturer", "high"),
    row("SRC_SUMPAR_001", "SUMPAR", "official_company", "https://www.sumpar.com/en/join-us/", "Official site lists SUMPAR at 134 Rue de la Forge Feret, 76520 Boos; metal parts/subassemblies for aeronautics.", "France", "134 Rue de la Forge Feret, 76520 Boos, France", "tier1 metal parts and technical subassemblies supplier", "high"),
    row("SRC_AMSAFE_001", "AmSafe", "official_company", "https://www.amsafe.com/contact-us/", "Contact page lists AmSafe headquarters at 1043 N. 47th Avenue, Phoenix, Arizona 85043.", "USA", "1043 N. 47th Avenue, Phoenix, Arizona 85043, USA", "tier1 safety restraint products supplier", "high"),
    row("SRC_ALCOA_001", "Alcoa", "official_company", "https://www.alcoa.com/global/en/who-we-are/locations", "Locations page lists Alcoa global locations and Pittsburgh global headquarters.", "USA / global depending commodity site", "Choose actual mine/refinery/smelter; Pittsburgh HQ is fallback", "tier4 aluminum/bauxite/alumina producer", "medium_high"),
    row("SRC_CONSTELLIUM_001", "Constellium C-TEC / Constellium", "official_company", "https://www.constellium.com/locations/c-tec", "Constellium page lists C-TEC Voreppe at Parc Economique Centr Alp, 725 rue Aristide Berges, Voreppe.", "France", "Parc Economique Centr Alp, 725 rue Aristide Berges, 38341 Voreppe Cedex, France", "tier3 aluminum alloys/transformation supplier", "medium_high"),
    row("SRC_AMAG_001", "AMAG Austria Metall", "official_company", "https://www.amag-al4u.com/impressum", "Imprint lists AMAG Austria Metall AG, Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria.", "Austria", "Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria", "tier3 aluminum casting/rolling/transformation supplier", "high"),
    row("SRC_TORAY_001", "Toray Industries", "official_company", "https://www.toray.com/aboutus/outline.html", "Corporate outline lists Toray Industries, Inc. in Tokyo 103-8666, Japan.", "Japan", "Tokyo 103-8666, Japan; choose actual production site from traceability", "chemical/polymer/carbon-fiber materials producer", "medium_high"),
    row("SRC_ARCELORMITTAL_001", "ArcelorMittal", "official_company", "https://luxembourg.arcelormittal.com/en/arcelormittal-in-luxembourg/headquarters", "Official page lists ArcelorMittal headquarters at 24-26 boulevard d Avranches, L-1160 Luxembourg.", "Luxembourg / production country depends steel plant", "24-26 boulevard d Avranches, L-1160 Luxembourg for HQ; choose actual steel plant", "tier4 steel and mining group / steel producer", "medium_high"),
    row("SRC_BASF_001", "BASF", "official_company", "https://www.basf.com/tr/en/careers/why-join-basf/basf-at-a-glance/basf-headquarters", "BASF page identifies Ludwigshafen, Germany as headquarters and largest production site.", "Germany", "Ludwigshafen am Rhein, Germany", "tier4 chemical producer", "medium_high"),
    row("SRC_HINDALCO_001", "Hindalco Industries", "official_company", "https://www.hindalco.com/contact-us/", "Contact page lists corporate/registered offices in Mumbai and describes aluminium/copper activities.", "India", "Use actual India plant; corporate office Mumbai is fallback", "tier4 aluminium/copper producer", "medium_high"),
    row("SRC_BAOWU_001", "China Baowu / Baosteel", "third_party_company_profile", "https://craft.co/baosteel/locations", "Company profile lists Baosteel/China Baowu headquarters in Shanghai; non-official fallback.", "China", "Baosteel Tower, Shanghai, China; choose actual steel plant", "tier4 steel producer", "medium"),
    row("SRC_AUBERT_001", "Aubert & Duval", "industry_association", "https://www.aerospace-cluster.fr/membre/aubert-duval/", "Aerospace Cluster page describes Aubert & Duval as metallurgical products/forgings supplier for aerospace.", "France", "Choose actual Aubert & Duval industrial site from traceability; Aubiere listing is fallback", "tier3 metallurgical transformation / forgings supplier", "medium_high"),
]

patterns = [
    (r"jamco niigata", "JAMCO Aircraft Interiors - Niigata", "Japan", "341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"jamco miyazaki", "JAMCO Aircraft Interiors - Miyazaki", "Japan", "8136-7 Tanocho-ko, Miyazaki, Miyazaki 889-1701, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"jamco philippines|jamco clark", "JAMCO Philippines Inc.", "Philippines", "N7000 Gil Puyat Avenue, Clark Civil Aviation Complex, Pampanga, Philippines", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"\bjamco\b", "JAMCO Aircraft Interiors", "Japan", "341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"mgr foamtex", "MGR Foamtex Ltd", "United Kingdom", "DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK", "aircraft upholstery / foam systems supplier", "SRC_MGR_001", "high", "tier1_or_tier2_second_transformation"),
    (r"lauak", "Groupe LAUAK", "France", "2245 Route de Minhotz, 64240 Hasparren, France", "aerostructures supplier", "SRC_LAUAK_001", "medium_high", "tier1"),
    (r"plastiservice", "Plastiservice Charleroi", "Belgium", "ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium", "plastics materials / processing supplier", "SRC_PLASTISERVICE_001", "high", "tier2_second_transformation"),
    (r"j c aero|jc aero", "J&C Aero", "Lithuania", "Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279", "aircraft interior provider", "SRC_JCAERO_001", "high", "tier1"),
    (r"stelia|airbus atlantique|airbus atlantic", "STELIA Aerospace / Airbus Atlantic", "France", "Rochefort, France", "premium passenger seat brand / cabin interior activity", "SRC_STELIA_AIRBUS_001", "medium_high", "oem_or_internal_site"),
    (r"safran", "Safran Seats / Safran internal group", "France", "Use actual Safran Seats site; HQ fallback Plaisir, France", "OEM/internal final integrator", "SRC_SAFRAN_SEATS_001", "high", "oem"),
    (r"figeac", "Figeac Aero", "France", "Zone industrielle de l'Aiguille, 46100 Figeac, France", "aerostructures / assemblies supplier", "SRC_FIGEAC_001", "high", "tier1"),
    (r"gattefin", "ETS Gattefin", "France", "201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France", "precision machining supplier", "SRC_GATTEFIN_001", "high", "tier1"),
    (r"segner|segnere", "Groupe Segnere / SEGNERE Ade", "France", "Z.I. du Toulicou, Ade, Occitanie 65100, France", "precision mechanics / sheet metal supplier", "SRC_SEGNERE_001", "medium_high", "tier1"),
    (r"celso", "Celso SAS", "France", "200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France", "foam / cellular materials transformer", "SRC_CELSO_001", "high", "tier1_or_tier2_second_transformation"),
    (r"\bach\b", "ACH", "France", "16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France", "aircraft upholstery / foams / seats supplier", "SRC_ACH_001", "high", "tier1_or_tier2_second_transformation"),
    (r"exsto|baule|baul", "EXSTO / Baule-Exsto Polymere", "France", "55 avenue de la Deportation, 26100 Romans-sur-Isere, France", "technical polymer / polyurethane supplier", "SRC_EXSTO_001", "high", "tier3_first_transformation"),
    (r"ancra", "Ancra International", "USA", "601 S Vincent Ave, Azusa, CA 91702, USA", "cargo restraint / fittings supplier", "SRC_ANCRA_001", "high", "tier1"),
    (r"ta aerospace", "TA Aerospace", "USA", "Valencia, California, USA - verify exact site", "aerospace clamps / insulation supplier", "SRC_TA_001", "medium", "tier1"),
    (r"e2ip", "e2ip technologies", "Canada", "1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada", "electronics / HMI supplier", "SRC_E2IP_001", "high", "tier2_second_transformation"),
    (r"thyssen|thyssenkrupp", "thyssenkrupp Materials France", "France", "Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France", "material distributor / supply-chain service provider", "SRC_THYSSEN_001", "high", "tier3_first_transformation"),
    (r"euralliage", "Euralliage Ile de France", "France", "3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France", "non-ferrous metals stockist/trader/cutting service", "SRC_EURALLIAGE_001", "high", "tier3_first_transformation"),
    (r"tata steel", "Tata Steel", "India", "Choose actual India plant from traceability", "steel producer / upstream material producer", "SRC_TATA_STEEL_001", "medium_high", "tier4_raw_material"),
    (r"dupont", "DuPont de Nemours", "USA or verified non-US site", "Choose product/site from DuPont locations and traceability", "chemical/material producer or transformer", "SRC_DUPONT_001", "medium_high", "tier2_second_transformation"),
    (r"nordic paper", "Nordic Paper", "Sweden / Norway / Canada", "Choose actual mill; Finland is not supported by official mill list", "specialty paper/pulp producer", "SRC_NORDIC_PAPER_001", "high", "tier4_raw_material_or_tier3_first_transformation"),
    (r"schroth", "SCHROTH Safety Products", "USA or Germany", "USA: Fort Lauderdale; Germany: Arnsberg", "safety restraint products supplier", "SRC_SCHROTH_001", "high", "tier2_second_transformation"),
    (r"anjou aero|anjou aero", "Anjou Aeronautique", "France", "4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France", "aeronautical interiors / manufacturing supplier", "SRC_ANJOU_001", "high", "tier1"),
    (r"senior aerospace", "Senior Aerospace Thailand", "Thailand", "789/115-116 Moo 1, Nhongkham Sriracha, Chonburi 20230, Thailand", "aerospace systems / cabin interiors manufacturer", "SRC_SENIOR_THAILAND_001", "high", "tier1"),
    (r"sumpar", "SUMPAR", "France", "134 Rue de la Forge Feret, 76520 Boos, France", "metal parts/subassemblies supplier", "SRC_SUMPAR_001", "high", "tier1"),
    (r"am safe|amsafe", "AmSafe", "USA", "1043 N. 47th Avenue, Phoenix, Arizona 85043, USA", "safety restraint products supplier", "SRC_AMSAFE_001", "high", "tier1"),
    (r"alcoa", "Alcoa", "USA / global commodity sites", "Choose actual mine/refinery/smelter; Pittsburgh HQ is fallback", "aluminum/bauxite/alumina producer", "SRC_ALCOA_001", "medium_high", "tier4_raw_material"),
    (r"constellium", "Constellium", "France / global depending production site", "C-TEC Voreppe, France is reference; choose production site if needed", "aluminum alloys/transformation supplier", "SRC_CONSTELLIUM_001", "medium_high", "tier3_first_transformation"),
    (r"austria metall|\bamag\b", "AMAG Austria Metall", "Austria", "Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria", "aluminum casting/rolling/transformation supplier", "SRC_AMAG_001", "high", "tier3_first_transformation"),
    (r"toray", "Toray Industries", "Japan", "Tokyo 103-8666, Japan; choose actual production site", "chemical/polymer/carbon-fiber materials producer", "SRC_TORAY_001", "medium_high", "tier3_first_transformation_or_tier4_raw_material"),
    (r"arcelor mittal|arcelormittal", "ArcelorMittal", "Luxembourg / production country depends steel plant", "HQ Luxembourg; choose actual steel plant", "steel and mining group / steel producer", "SRC_ARCELORMITTAL_001", "medium_high", "tier4_raw_material"),
    (r"basf", "BASF", "Germany", "Ludwigshafen am Rhein, Germany", "chemical producer", "SRC_BASF_001", "medium_high", "tier4_raw_material"),
    (r"hindalco", "Hindalco Industries", "India", "Use actual India plant; corporate office Mumbai is fallback", "aluminium/copper producer", "SRC_HINDALCO_001", "medium_high", "tier4_raw_material"),
    (r"china baowu|baowu", "China Baowu / Baosteel", "China", "Baosteel Tower, Shanghai; choose actual steel plant", "steel producer", "SRC_BAOWU_001", "medium", "tier4_raw_material"),
    (r"aubert|duval", "Aubert & Duval", "France", "Choose actual industrial site from traceability", "metallurgical transformation / forgings supplier", "SRC_AUBERT_001", "medium_high", "tier3_first_transformation"),
]


def match_source(finding):
    text = norm(finding.get("supplier_name")) + " " + norm(finding.get("geocode_query"))
    for pat, canonical, country, address, role, source_id, confidence, proposed_role_hint in patterns:
        if re.search(pat, text):
            return {
                "canonical_supplier": canonical,
                "proposed_country": country,
                "proposed_site_address": address,
                "proposed_role": role,
                "proposed_role_hint": proposed_role_hint,
                "source_ids": source_id,
                "source_confidence": confidence,
            }
    return {
        "canonical_supplier": "",
        "proposed_country": "",
        "proposed_site_address": "",
        "proposed_role": "",
        "proposed_role_hint": "",
        "source_ids": "",
        "source_confidence": "none",
    }


def recommendation(finding, matched):
    category = finding["category"]
    role = finding.get("role_hint", "")
    if category in {"DATASET_MASS_ZERO_REMAINING", "MASS_INVALID"}:
        return "Reload mass from BOM/PLM/weighing source; if unknown set mass_kg=null and mass_status=missing, not 0.0.", "data_source_required"
    if category in {"DATASET_MARKET_SHARE_EMPTY", "MARKET_SHARE_INVALID"}:
        return "Reload market_share_pct as numeric 0-100 or set null with explicit missing status; do not keep empty string.", "data_source_required"
    if category == "RAW_MATERIALS_EMPTY":
        return "Populate raw_materials from material classification/BOM or set raw_materials_status=missing.", "data_source_required"
    if category == "COUNTRY_CENTROID_USED":
        if matched["source_ids"]:
            return f"Country centroid is not site-grade. Re-geocode from source-backed address for {matched['canonical_supplier']}: {matched['proposed_site_address']}; keep centroid only as fallback metadata.", "source_backed_geocode_required"
        return "Country centroid is not site-grade. Re-geocode from verified supplier site address; keep centroid only as fallback metadata.", "geocode_required"
    if category in {"COORDINATE_OUTSIDE_LOCATION_COUNTRY", "GEOCODE_QUERY_LOCATION_COUNTRY_MISMATCH", "COUNTRY_FIELD_LOCATION_MISMATCH", "LOCATION_INVALID", "GEOCODE_PROVIDER_MISSING", "LOCATION_NONSTANDARD_LABEL"}:
        if matched["source_ids"]:
            return f"Normalize supplier to {matched['canonical_supplier']}; set/verify country as {matched['proposed_country']}; use site/address: {matched['proposed_site_address']}; recompute lat/lon and preserve old values in audit history.", "source_backed_correction"
        return "Normalize country/location fields and re-geocode from a verified site address. Current name/location/query/coordinates are not sufficiently consistent.", "needs_source_or_geocode"
    if category in {"ROLE_HINT_VAGUE", "ROLE_HINT_PLAUSIBILITY_REVIEW"}:
        if matched["source_ids"]:
            return f"Replace or validate role_hint {role!r}; proposed role_hint={matched['proposed_role_hint']}. Source-backed business role: {matched['proposed_role']}.", "source_backed_role_review"
        return f"Replace or validate role_hint {role!r} with a canonical tier after business validation.", "role_mapping_required"
    if category == "MULTIPLE_PRIMARY_SUPPLIERS_PER_ROLE":
        return "For each record + role_hint, keep one primary supplier or add allocation shares. Multiple is_primary=true cannot be interpreted without shares.", "business_rule_required"
    if category in {"DUPLICATE_SUPPLIER_SAME_RECORD_ROLE", "SAME_SUPPLIER_MULTIPLE_ROLES_SAME_RECORD"}:
        return "Deduplicate by canonical supplier_id + site_id + role_hint; merge notes/source_ids and keep only justified repeated roles.", "dedupe_rule"
    if category == "OEM_ENTRY_IN_SUPPLIERS_LIST":
        return "Move OEM/internal final integrator entries out of external suppliers into oem/internal_site/internal_flow table.", "schema_fix"
    if category == "LOGISTICS_PROVIDER_IN_SUPPLIERS_LIST":
        return "Move logistics providers from suppliers list to transport_provider/route_leg structure.", "schema_fix"
    if category in {"TRANSPORT_MODE_NOT_A_TRANSPORT_MODE", "TRANSPORT_MODE_NOT_CANONICAL"}:
        return "Normalize transport modes to atomic values truck/ship/rail/air/pipeline and move provider/internal labels to separate fields.", "schema_fix"
    if category == "SUPPLIER_NAME_MALFORMED":
        return "Clean supplier name: fix placeholders/parentheses and move notes/location into structured fields.", "data_cleaning"
    if category == "SYSTEM_SPELLING_NORMALIZATION":
        return "Normalize controlled vocabulary/display label for system names.", "data_cleaning"
    if category == "COMPONENT_IS_NOT_A_MATERIAL_OR_PART":
        return "Move transport/packaging pseudo-components out of part/material records.", "schema_fix"
    if category.startswith("MISSING_ROLE"):
        return "Complete required role from purchasing/BOM traceability or mark role explicitly unknown with reason.", "data_source_required"
    if category == "NO_PRIMARY_SUPPLIER_FOR_ROLE":
        return "Set one primary supplier for this role or provide allocation shares.", "business_rule_required"
    return "Review and correct according to audit category.", "needs_review"


def main():
    findings = list(csv.DictReader(AUDIT.open(encoding="utf-8-sig")))
    source_fields = ["source_id", "entity", "source_type", "url", "evidence", "canonical_country", "canonical_site_address", "canonical_role", "confidence"]
    with OUT_SRC.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=source_fields)
        writer.writeheader()
        writer.writerows(sources)

    out_rows = []
    for finding in findings:
        matched = match_source(finding)
        action, status = recommendation(finding, matched)
        out = dict(finding)
        out.update(matched)
        out["recommended_action"] = action
        out["correction_status"] = status
        out_rows.append(out)

    extra_fields = ["canonical_supplier", "proposed_country", "proposed_site_address", "proposed_role", "proposed_role_hint", "recommended_action", "correction_status", "source_ids", "source_confidence"]
    with OUT_CORR.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(findings[0].keys()) + extra_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    severity_counts = Counter(row["severity"] for row in findings)
    category_counts = Counter(row["category"] for row in findings)
    status_counts = Counter(row["correction_status"] for row in out_rows)
    source_hits = Counter(bool(row["source_ids"]) for row in out_rows)
    source_id_counts = Counter(row["source_ids"] for row in out_rows if row["source_ids"])

    lines = [
        "# Reference corrections sourcees - output8_GEO_normalized.json",
        "",
        "Ce fichier reprend l audit de `analysis/output8_GEO_normalized.json` et associe chaque anomalie a une correction proposee. Le JSON source n a pas ete modifie.",
        "",
        "## Fichiers",
        "",
        f"- Audit detaille: `{AUDIT.as_posix()}`",
        f"- Corrections detaillees: `{OUT_CORR.as_posix()}`",
        f"- Registre des sources: `{OUT_SRC.as_posix()}`",
        "",
        "## Couverture",
        "",
        f"- Lignes d audit reprises: {len(findings)}",
        "- Severites: " + ", ".join(f"{key}={value}" for key, value in severity_counts.items()),
        "- Statuts de correction: " + ", ".join(f"{key}={value}" for key, value in status_counts.most_common()),
        f"- Lignes rattachees a une source metier: {source_hits[True]}",
        f"- Lignes sans source directe: {source_hits[False]}",
        "",
        "## Corrections sourcees prioritaires",
        "",
        "- **Plastiservice**: corriger les lignes `location=France` mais `geocode_query=Belgique` vers Belgium/Charleroi.",
        "- **J&C Aero**: remplacer les coordonnees Bresil/hors Lituanie par le site officiel Vilnius, Lithuania.",
        "- **Anjou Aero**: remplacer les centroides USA associes a Anjou Aero par Chanteloup-les-Vignes, France.",
        "- **Schroth**: resoudre USA vs Allemagne: si flux USA, utiliser Fort Lauderdale; si flux EMEA, utiliser Arnsberg.",
        "- **DuPont**: ne pas melanger `location=USA` avec coordonnees France; choisir le site DuPont traceable au produit.",
        "- **Nordic Paper**: la source officielle ne confirme pas Finlande; choisir un moulin Sweden/Norway/Canada selon la matiere.",
        "- **JAMCO**: les sites Niigata, Miyazaki et Philippines sont identifiables; dedupliquer les repetitions dans chaque record.",
        "- **Safran**: garder Safran en OEM/internal integrator, pas comme fournisseur externe Tier 1.",
        "- **Roles vagues**: remplacer `material` et `transformation` par tier2/tier3/tier4 selon le role source et la matiere achetee.",
        "",
        "## Sources retenues",
        "",
    ]
    for source in sources:
        lines.append(f"- `{source['source_id']}` - {source['entity']} ({source['source_type']}): {source['canonical_country']}; {source['canonical_site_address']}; role: {source['canonical_role']}; {source['url']}")
    lines += ["", "## Regles par categorie", ""]
    for category, count in category_counts.most_common():
        lines.append(f"### {category} ({count})")
        for example in [row for row in out_rows if row["category"] == category][:3]:
            record = f"R{example['record_index']}" if example["record_index"] else "DATASET"
            supplier = example["supplier_name"] or "-"
            source = example["source_ids"] or "none"
            lines.append(f"- {record}; supplier={supplier}; role={example['role_hint']}; status={example['correction_status']}; sources={source}; action={example['recommended_action']}")
        lines.append("")
    lines += [
        "## Limites",
        "",
        "- Les sources web confirment adresses/roles generiques, mais pas automatiquement le site effectivement utilise dans la supply Safran.",
        "- Les masses, parts de marche, roles primaires et allocations fournisseurs doivent etre corriges depuis BOM/PLM/ERP/achats/logistique.",
        "- Les adresses proposees doivent etre re-geocodees proprement avant correction du JSON.",
    ]
    OUT_MD.write_text("\\n".join(lines) + "\\n", encoding="utf-8")

    print(f"wrote {OUT_CORR} rows={len(out_rows)}")
    print(f"wrote {OUT_SRC} rows={len(sources)}")
    print(f"wrote {OUT_MD}")
    print("status", dict(status_counts))
    print("source_hits", source_hits[True], "no_source", source_hits[False])
    print("top_sources", source_id_counts.most_common(15))


if __name__ == "__main__":
    main()
