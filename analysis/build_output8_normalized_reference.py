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
    row("SRC_JAMCO_001", "FRN-1E9DB09C4FE35C", "official_company", "https://sources.invalid/FRN-1E9DB09C4FE35C/27d6c9719cd5b607", "JAMCO group page lists Niigata, Miyazaki and Philippines aircraft-interiors sites.", "Japan / Philippines depending site", "Niigata: 341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822; Miyazaki: 8136-7 Tanocho-ko, Miyazaki 889-1701; Philippines: N7000 Gil Puyat Avenue, Clark Civil Aviation Complex, Pampanga.", "tier1 aircraft interiors manufacturer", "high"),
    row("SRC_MGR_001", "FRN-213AAC10F8FF68", "official_company", "https://sources.invalid/FRN-213AAC10F8FF68/b35963cfb89ecaa9", "Contact page gives DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK.", "United Kingdom", "DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK", "aircraft upholstery / foam systems supplier", "high"),
    row("SRC_LAUAK_001", "FRN-C1DF555DA868BF", "official_company", "https://sources.invalid/FRN-C1DF555DA868BF/84469f6de2ef2075", "LAUAK sites page lists Hasparren and other group sites.", "France, plus other group countries depending site", "2245 Route de Minhotz, 64240 Hasparren, France", "aerostructures / sheet metal / machining / structural assembly supplier", "medium_high"),
    row("SRC_FRN-D16128C2D1AA8B_001", "FRN-6DA33580D77667", "official_company", "https://sources.invalid/FRN-6DA33580D77667/0aa01c2bc1c764f4", "Locations page lists FRN-6DA33580D77667 at ZI de Jumet, Allee Centrale 72, B-6040 Charleroi.", "Belgium", "ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium", "tier2 plastics materials / processing supplier", "high"),
    row("SRC_JCAERO_001", "FRN-2EC56F8EB8EC02", "official_company", "https://sources.invalid/FRN-2EC56F8EB8EC02/da136f17c3e151ba", "Contact page lists Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279.", "Lithuania", "Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279", "tier1 aircraft interior provider", "high"),
    row("SRC_FRN-4F3EF5C6442315_FRN-1045D929655FAF_001", "FRN-4F3EF5C6442315", "official_group", "https://sources.invalid/FRN-4F3EF5C6442315/6c542b1300158f44", "FRN-1045D929655FAF identifies FRN-4F3EF5C6442315 as FRN-4F3EF5C6442315 premium passenger seat brand.", "France", "Rochefort, France when no better site is proven", "premium passenger seat brand / FRN-4F3EF5C6442315 cabin interiors", "medium_high"),
    row("SRC_FRN-AA08AEDDCB94EB_001", "FRN-AA08AEDDCB94EB", "official_group", "https://sources.invalid/FRN-AA08AEDDCB94EB/a3382db34064c23a", "FRN-F1F796DB13C8E2 locations list FRN-AA08AEDDCB94EB sites including Plaisir, Issoudun, Saint-Crepin-Ibouvillers and Gainesville.", "France / USA / UK depending actual site", "Use actual FRN-AA08AEDDCB94EB site; HQ fallback: 61 Rue Pierre Curie, 78373 Plaisir, France", "OEM/internal final integrator in this dataset context", "high"),
    row("SRC_FIGEAC_001", "FRN-8461B2D08E3D4E", "official_company", "https://sources.invalid/FRN-8461B2D08E3D4E/91da9e1ad71e7632", "Contact page lists Zone industrielle de l Aiguille, 46100 Figeac, France.", "France", "Zone industrielle de l'Aiguille, 46100 Figeac, France", "tier1 aerostructures / assemblies supplier", "high"),
    row("SRC_FRN-FCB0C890EFA2B8_001", "FRN-0B41BF5B9E4B4E", "official_company", "https://sources.invalid/FRN-0B41BF5B9E4B4E/3edb20f3674cd12c", "Official site gives 201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre and aerospace activity.", "France", "201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France", "tier1 precision machining supplier", "high"),
    row("SRC_FRN-D0B6DB0F437592_001", "FRN-999053838C0E1C", "industry_association", "https://sources.invalid/FRN-999053838C0E1C/dfaa5e460d73f239", "SPACE Aero member page lists FRN-D0B6DB0F437592 Ade in France with precision mechanics, sheet metal and structural assembly.", "France", "Z.I. du Toulicou, Ade, Occitanie 65100, France", "tier1 precision mechanics / sheet metal / assembly supplier", "medium_high"),
    row("SRC_FRN-67CD5F21738C93_001", "FRN-73FE254CB14818", "official_company", "https://sources.invalid/FRN-73FE254CB14818/66f09a5e8ae14c77", "Contact page lists FRN-73FE254CB14818, 200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols.", "France", "200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France", "foam and cellular materials transformer", "high"),
    row("SRC_FRN-72A8D622F0F88D_001", "FRN-72A8D622F0F88D", "official_company", "https://sources.invalid/FRN-72A8D622F0F88D/324836d380be55e2", "Contact page lists 16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers.", "France", "16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France", "aircraft upholstery / foams / seats supplier", "high"),
    row("SRC_EXSTO_001", "FRN-33013E3321A5B5", "official_company", "https://sources.invalid/FRN-33013E3321A5B5/2664e4021d8fa64d", "EXSTO contact page gives headquarter at 55 avenue de la Deportation, 26100 Romans-sur-Isere.", "France", "55 avenue de la Deportation, 26100 Romans-sur-Isere, France", "technical polymer / polyurethane supplier", "high"),
    row("SRC_ANCRA_001", "FRN-5BB9473F176CD6", "official_company", "https://sources.invalid/FRN-5BB9473F176CD6/820ae6a63963e7f0", "FRN-5BB9473F176CD6 Division lists FRN-51245894531FE9, 601 S Vincent Ave, Azusa, CA 91702.", "USA", "601 S Vincent Ave, Azusa, CA 91702, USA", "tier1 cargo restraint / fittings / aircraft systems supplier", "high"),
    row("SRC_TA_001", "FRN-4DC00ECEFB8526", "official_company", "https://sources.invalid/FRN-4DC00ECEFB8526/175304c3b4cf9832", "Official site describes aerospace clamping devices, thermal insulation products and engineered solutions.", "USA", "Valencia, California, USA - verify exact site address before geocoding", "tier1 aerospace clamps / insulation supplier", "medium"),
    row("SRC_FRN-869E1A8BB344FD_001", "FRN-FD0761D13CF2C9", "official_company", "https://sources.invalid/FRN-FD0761D13CF2C9/128ea21c477639ca", "Contact page lists Design & Manufacturing Center at 1455, 32nd Avenue, Lachine, QC H8T 3J1.", "Canada", "1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada", "tier2 electronics / HMI supplier", "high"),
    row("SRC_THYSSEN_001", "FRN-8D94FBDCC3B3B5", "official_company", "https://sources.invalid/FRN-8D94FBDCC3B3B5/219f77fbb72670ab", "France location page lists Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas and materials/supply-chain capabilities.", "France", "Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France", "tier3 material distributor / supply-chain service provider", "high"),
    row("SRC_FRN-C3B826345B6812_001", "FRN-6EF3EF62BA6339", "official_company", "https://sources.invalid/FRN-6EF3EF62BA6339/ebbb89b3f29571fb", "Coordinates page lists 3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse.", "France", "3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France", "tier3 non-ferrous metals stockist/trader/cutting service", "high"),
    row("SRC_FRN-5AA9E59DA0B02F_001", "FRN-5AA9E59DA0B02F", "official_group", "https://sources.invalid/FRN-5AA9E59DA0B02F/82460ad4d7fb1be8", "Tata group page states FRN-5AA9E59DA0B02F operates in India in Jamshedpur, Gamharia, Kalinganagar and Meramandali.", "India", "Choose actual India plant from traceability", "tier4 steel producer / upstream material producer", "medium_high"),
    row("SRC_DUPONT_001", "FRN-0B3DAD918C8F64", "official_company", "https://sources.invalid/FRN-0B3DAD918C8F64/7c1160d3a5c2e2b5", "DuPont locations page lists Wilmington, Delaware global headquarters and many global sites.", "USA unless a specific non-US manufacturing site is proven", "Choose product/site from DuPont locations and traceability", "tier2 chemical/material producer or transformer", "medium_high"),
    row("SRC_FRN-AC50E317D82C5C_001", "FRN-AC50E317D82C5C", "official_company", "https://sources.invalid/FRN-AC50E317D82C5C/6d21aa3805bcbba5", "Contact/about pages list mills in Sweden, Norway and Canada; not Finland.", "Sweden / Norway / Canada depending mill", "Choose actual mill: Saffle/Amotfors/Backhammar, Sweden; Greaker, Norway; Quebec, Canada", "specialty paper/pulp producer", "high"),
    row("SRC_FRN-BDF19DDAD7E188_001", "FRN-C2C13D47AFDB04", "official_company", "https://sources.invalid/FRN-C2C13D47AFDB04/816ec8e4af24274b", "Contact page lists FRN-C2C13D47AFDB04 GmbH in Arnsberg, Germany and FRN-C2C13D47AFDB04 LLC in Fort Lauderdale, USA.", "Germany or USA depending actual site", "Germany: Arnsberg; USA: 5320 NW 35th Ave, Fort Lauderdale, FL 33309", "safety restraint products supplier", "high"),
    row("SRC_ANJOU_001", "FRN-82CCA67E25D130", "official_company", "https://sources.invalid/FRN-82CCA67E25D130/4f905d53cbd8bdca", "Contact page lists 4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France.", "France", "4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France", "tier1 aeronautical interiors / manufacturing supplier", "high"),
    row("SRC_FRN-4BCB03E5586F0F_THAILAND_001", "FRN-98C883F706EF89", "official_company", "https://sources.invalid/FRN-98C883F706EF89/cb1a7c2c794d8d8e", "Contact page lists factories at 789/115-116 and 789/198 Moo 1, Nhongkham Sriracha, Chonburi.", "Thailand", "789/115-116 Moo 1, Nhongkham Sriracha, Chonburi 20230, Thailand", "tier1 high-precision aerospace systems / cabin interiors manufacturer", "high"),
    row("SRC_FRN-72A106312E8F95_001", "FRN-72A106312E8F95", "official_company", "https://sources.invalid/FRN-72A106312E8F95/800dbe576b2ac96b", "Official site lists FRN-72A106312E8F95 at 134 Rue de la Forge Feret, 76520 Boos; metal parts/subassemblies for aeronautics.", "France", "134 Rue de la Forge Feret, 76520 Boos, France", "tier1 metal parts and technical subassemblies supplier", "high"),
    row("SRC_FRN-D9C48086C34DAF_001", "FRN-D9C48086C34DAF", "official_company", "https://sources.invalid/FRN-D9C48086C34DAF/de636099c011a9ce", "Contact page lists FRN-D9C48086C34DAF headquarters at 1043 N. 47th Avenue, Phoenix, Arizona 85043.", "USA", "1043 N. 47th Avenue, Phoenix, Arizona 85043, USA", "tier1 safety restraint products supplier", "high"),
    row("SRC_FRN-34B2AC7037114C_001", "FRN-34B2AC7037114C", "official_company", "https://sources.invalid/FRN-34B2AC7037114C/a51ccd24c98ad4c1", "Locations page lists FRN-34B2AC7037114C global locations and Pittsburgh global headquarters.", "USA / global depending commodity site", "Choose actual mine/refinery/smelter; Pittsburgh HQ is fallback", "tier4 aluminum/bauxite/alumina producer", "medium_high"),
    row("SRC_FRN-798BE9ED657B85_001", "FRN-2793CEA5F65B7B", "official_company", "https://sources.invalid/FRN-2793CEA5F65B7B/be0bd9e99be57dc3", "FRN-798BE9ED657B85 page lists C-TEC Voreppe at Parc Economique Centr Alp, 725 rue Aristide Berges, Voreppe.", "France", "Parc Economique Centr Alp, 725 rue Aristide Berges, 38341 Voreppe Cedex, France", "tier3 aluminum alloys/transformation supplier", "medium_high"),
    row("SRC_AMAG_001", "FRN-CD09D021B366DB", "official_company", "https://sources.invalid/FRN-CD09D021B366DB/0496d3f6ce5767be", "Imprint lists FRN-CD09D021B366DB AG, Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria.", "Austria", "Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria", "tier3 aluminum casting/rolling/transformation supplier", "high"),
    row("SRC_FRN-9C546CCC918C61_001", "FRN-0F56088BEA4986", "official_company", "https://sources.invalid/FRN-0F56088BEA4986/9b38177dfc07ec2c", "Corporate outline lists FRN-0F56088BEA4986, Inc. in Tokyo 103-8666, Japan.", "Japan", "Tokyo 103-8666, Japan; choose actual production site from traceability", "chemical/polymer/carbon-fiber materials producer", "medium_high"),
    row("SRC_FRN-3C5607FC501E5A_001", "FRN-3C5607FC501E5A", "official_company", "https://sources.invalid/FRN-3C5607FC501E5A/050bd0bdef2c8aaf", "Official page lists FRN-3C5607FC501E5A headquarters at 24-26 boulevard d Avranches, L-1160 Luxembourg.", "Luxembourg / production country depends steel plant", "24-26 boulevard d Avranches, L-1160 Luxembourg for HQ; choose actual steel plant", "tier4 steel and mining group / steel producer", "medium_high"),
    row("SRC_FRN-301ED6D3E70080_001", "FRN-301ED6D3E70080", "official_company", "https://sources.invalid/FRN-301ED6D3E70080/b2bc132e9d685730", "FRN-301ED6D3E70080 page identifies Ludwigshafen, Germany as headquarters and largest production site.", "Germany", "Ludwigshafen am Rhein, Germany", "tier4 chemical producer", "medium_high"),
    row("SRC_FRN-191F6AC0669F77_001", "FRN-60C89B8D6563EA", "official_company", "https://sources.invalid/FRN-60C89B8D6563EA/c7abe5e6a7f3ef6b", "Contact page lists corporate/registered offices in Mumbai and describes aluminium/copper activities.", "India", "Use actual India plant; corporate office Mumbai is fallback", "tier4 aluminium/copper producer", "medium_high"),
    row("SRC_BAOWU_001", "FRN-CF71418802439F", "third_party_company_profile", "https://sources.invalid/FRN-CF71418802439F/61e2b40f4124dc67", "Company profile lists Baosteel/FRN-336EE447D72F75 headquarters in Shanghai; non-official fallback.", "China", "Baosteel Tower, Shanghai, China; choose actual steel plant", "tier4 steel producer", "medium"),
    row("SRC_AUBERT_001", "FRN-83186B5AEF84D8", "industry_association", "https://sources.invalid/FRN-83186B5AEF84D8/8b96b5b078b0913d", "Aerospace Cluster page describes FRN-83186B5AEF84D8 as metallurgical products/forgings supplier for aerospace.", "France", "Choose actual FRN-83186B5AEF84D8 industrial site from traceability; Aubiere listing is fallback", "tier3 metallurgical transformation / forgings supplier", "medium_high"),
]

patterns = [
    (r"FRN-4B0BBE731CA526", "FRN-B4E809AFDBFA0B", "Japan", "341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"FRN-A215F89D6DB387", "FRN-19277B67029E73", "Japan", "8136-7 Tanocho-ko, Miyazaki, Miyazaki 889-1701, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"jamco philippines|jamco clark", "FRN-AA9FC43191C9DB", "Philippines", "N7000 Gil Puyat Avenue, Clark Civil Aviation Complex, Pampanga, Philippines", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"\bjamco\b", "JAMCO Aircraft Interiors", "Japan", "341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan", "tier1 aircraft interiors manufacturer", "SRC_JAMCO_001", "high", "tier1"),
    (r"FRN-54423E8FD293B7", "FRN-213AAC10F8FF68", "United Kingdom", "DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK", "aircraft upholstery / foam systems supplier", "SRC_MGR_001", "high", "tier1_or_tier2_second_transformation"),
    (r"lauak", "FRN-C1DF555DA868BF", "France", "2245 Route de Minhotz, 64240 Hasparren, France", "aerostructures supplier", "SRC_LAUAK_001", "medium_high", "tier1"),
    (r"FRN-D16128C2D1AA8B", "FRN-6DA33580D77667", "Belgium", "ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium", "plastics materials / processing supplier", "SRC_FRN-D16128C2D1AA8B_001", "high", "tier2_second_transformation"),
    (r"j c aero|jc aero", "FRN-2EC56F8EB8EC02", "Lithuania", "Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279", "aircraft interior provider", "SRC_JCAERO_001", "high", "tier1"),
    (r"FRN-4F3EF5C6442315|FRN-4F3EF5C6442315|FRN-4F3EF5C6442315", "FRN-4F3EF5C6442315", "France", "Rochefort, France", "premium passenger seat brand / cabin interior activity", "SRC_FRN-4F3EF5C6442315_FRN-1045D929655FAF_001", "medium_high", "oem_or_internal_site"),
    (r"FRN-F1F796DB13C8E2", "FRN-AA08AEDDCB94EB", "France", "Use actual FRN-AA08AEDDCB94EB site; HQ fallback Plaisir, France", "OEM/internal final integrator", "SRC_FRN-AA08AEDDCB94EB_001", "high", "oem"),
    (r"figeac", "FRN-8461B2D08E3D4E", "France", "Zone industrielle de l'Aiguille, 46100 Figeac, France", "aerostructures / assemblies supplier", "SRC_FIGEAC_001", "high", "tier1"),
    (r"FRN-FCB0C890EFA2B8", "FRN-0B41BF5B9E4B4E", "France", "201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France", "precision machining supplier", "SRC_FRN-FCB0C890EFA2B8_001", "high", "tier1"),
    (r"segner|FRN-D0B6DB0F437592", "FRN-999053838C0E1C", "France", "Z.I. du Toulicou, Ade, Occitanie 65100, France", "precision mechanics / sheet metal supplier", "SRC_FRN-D0B6DB0F437592_001", "medium_high", "tier1"),
    (r"FRN-67CD5F21738C93", "FRN-73FE254CB14818", "France", "200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France", "foam / cellular materials transformer", "SRC_FRN-67CD5F21738C93_001", "high", "tier1_or_tier2_second_transformation"),
    (r"\bach\b", "FRN-72A8D622F0F88D", "France", "16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France", "aircraft upholstery / foams / seats supplier", "SRC_FRN-72A8D622F0F88D_001", "high", "tier1_or_tier2_second_transformation"),
    (r"exsto|baule|baul", "FRN-33013E3321A5B5", "France", "55 avenue de la Deportation, 26100 Romans-sur-Isere, France", "technical polymer / polyurethane supplier", "SRC_EXSTO_001", "high", "tier3_first_transformation"),
    (r"ancra", "FRN-51245894531FE9", "USA", "601 S Vincent Ave, Azusa, CA 91702, USA", "cargo restraint / fittings supplier", "SRC_ANCRA_001", "high", "tier1"),
    (r"FRN-4DC00ECEFB8526", "FRN-4DC00ECEFB8526", "USA", "Valencia, California, USA - verify exact site", "aerospace clamps / insulation supplier", "SRC_TA_001", "medium", "tier1"),
    (r"FRN-869E1A8BB344FD", "FRN-FD0761D13CF2C9", "Canada", "1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada", "electronics / HMI supplier", "SRC_FRN-869E1A8BB344FD_001", "high", "tier2_second_transformation"),
    (r"thyssen|thyssenkrupp", "FRN-8D94FBDCC3B3B5", "France", "Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France", "material distributor / supply-chain service provider", "SRC_THYSSEN_001", "high", "tier3_first_transformation"),
    (r"FRN-C3B826345B6812", "FRN-6EF3EF62BA6339", "France", "3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France", "non-ferrous metals stockist/trader/cutting service", "SRC_FRN-C3B826345B6812_001", "high", "tier3_first_transformation"),
    (r"FRN-5AA9E59DA0B02F", "FRN-5AA9E59DA0B02F", "India", "Choose actual India plant from traceability", "steel producer / upstream material producer", "SRC_FRN-5AA9E59DA0B02F_001", "medium_high", "tier4_raw_material"),
    (r"dupont", "FRN-0B3DAD918C8F64", "USA or verified non-US site", "Choose product/site from DuPont locations and traceability", "chemical/material producer or transformer", "SRC_DUPONT_001", "medium_high", "tier2_second_transformation"),
    (r"FRN-AC50E317D82C5C", "FRN-AC50E317D82C5C", "Sweden / Norway / Canada", "Choose actual mill; Finland is not supported by official mill list", "specialty paper/pulp producer", "SRC_FRN-AC50E317D82C5C_001", "high", "tier4_raw_material_or_tier3_first_transformation"),
    (r"FRN-BDF19DDAD7E188", "FRN-C2C13D47AFDB04", "USA or Germany", "USA: Fort Lauderdale; Germany: Arnsberg", "safety restraint products supplier", "SRC_FRN-BDF19DDAD7E188_001", "high", "tier2_second_transformation"),
    (r"FRN-E4E6AFF0074745|FRN-E4E6AFF0074745", "FRN-82CCA67E25D130", "France", "4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France", "aeronautical interiors / manufacturing supplier", "SRC_ANJOU_001", "high", "tier1"),
    (r"FRN-D2BA5EA122CAA7", "FRN-98C883F706EF89", "Thailand", "789/115-116 Moo 1, Nhongkham Sriracha, Chonburi 20230, Thailand", "aerospace systems / cabin interiors manufacturer", "SRC_FRN-4BCB03E5586F0F_THAILAND_001", "high", "tier1"),
    (r"FRN-72A106312E8F95", "FRN-72A106312E8F95", "France", "134 Rue de la Forge Feret, 76520 Boos, France", "metal parts/subassemblies supplier", "SRC_FRN-72A106312E8F95_001", "high", "tier1"),
    (r"FRN-56B73048A39DA4|FRN-D9C48086C34DAF", "FRN-D9C48086C34DAF", "USA", "1043 N. 47th Avenue, Phoenix, Arizona 85043, USA", "safety restraint products supplier", "SRC_FRN-D9C48086C34DAF_001", "high", "tier1"),
    (r"FRN-34B2AC7037114C", "FRN-34B2AC7037114C", "USA / global commodity sites", "Choose actual mine/refinery/smelter; Pittsburgh HQ is fallback", "aluminum/bauxite/alumina producer", "SRC_FRN-34B2AC7037114C_001", "medium_high", "tier4_raw_material"),
    (r"FRN-798BE9ED657B85", "FRN-798BE9ED657B85", "France / global depending production site", "C-TEC Voreppe, France is reference; choose production site if needed", "aluminum alloys/transformation supplier", "SRC_FRN-798BE9ED657B85_001", "medium_high", "tier3_first_transformation"),
    (r"FRN-6C9C7F20179A2A|\bamag\b", "FRN-CD09D021B366DB", "Austria", "Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria", "aluminum casting/rolling/transformation supplier", "SRC_AMAG_001", "high", "tier3_first_transformation"),
    (r"FRN-9C546CCC918C61", "FRN-0F56088BEA4986", "Japan", "Tokyo 103-8666, Japan; choose actual production site", "chemical/polymer/carbon-fiber materials producer", "SRC_FRN-9C546CCC918C61_001", "medium_high", "tier3_first_transformation_or_tier4_raw_material"),
    (r"FRN-3C5607FC501E5A|FRN-3C5607FC501E5A", "FRN-3C5607FC501E5A", "Luxembourg / production country depends steel plant", "HQ Luxembourg; choose actual steel plant", "steel and mining group / steel producer", "SRC_FRN-3C5607FC501E5A_001", "medium_high", "tier4_raw_material"),
    (r"FRN-301ED6D3E70080", "FRN-301ED6D3E70080", "Germany", "Ludwigshafen am Rhein, Germany", "chemical producer", "SRC_FRN-301ED6D3E70080_001", "medium_high", "tier4_raw_material"),
    (r"FRN-191F6AC0669F77", "FRN-60C89B8D6563EA", "India", "Use actual India plant; corporate office Mumbai is fallback", "aluminium/copper producer", "SRC_FRN-191F6AC0669F77_001", "medium_high", "tier4_raw_material"),
    (r"FRN-336EE447D72F75|baowu", "FRN-CF71418802439F", "China", "Baosteel Tower, Shanghai; choose actual steel plant", "steel producer", "SRC_BAOWU_001", "medium", "tier4_raw_material"),
    (r"aubert|duval", "FRN-83186B5AEF84D8", "France", "Choose actual industrial site from traceability", "metallurgical transformation / forgings supplier", "SRC_AUBERT_001", "medium_high", "tier3_first_transformation"),
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
        "- **FRN-D16128C2D1AA8B**: corriger les lignes `location=France` mais `geocode_query=Belgique` vers Belgium/Charleroi.",
        "- **FRN-2EC56F8EB8EC02**: remplacer les coordonnees Bresil/hors Lituanie par le site officiel Vilnius, Lithuania.",
        "- **FRN-E4E6AFF0074745**: remplacer les centroides USA associes a FRN-E4E6AFF0074745 par Chanteloup-les-Vignes, France.",
        "- **FRN-BDF19DDAD7E188**: resoudre USA vs Allemagne: si flux USA, utiliser Fort Lauderdale; si flux EMEA, utiliser Arnsberg.",
        "- **DuPont**: ne pas melanger `location=USA` avec coordonnees France; choisir le site DuPont traceable au produit.",
        "- **FRN-AC50E317D82C5C**: la source officielle ne confirme pas Finlande; choisir un moulin Sweden/Norway/Canada selon la matiere.",
        "- **JAMCO**: les sites Niigata, Miyazaki et Philippines sont identifiables; dedupliquer les repetitions dans chaque record.",
        "- **FRN-F1F796DB13C8E2**: garder FRN-F1F796DB13C8E2 en OEM/internal integrator, pas comme fournisseur externe Tier 1.",
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
        "- Les sources web confirment adresses/roles generiques, mais pas automatiquement le site effectivement utilise dans la supply FRN-F1F796DB13C8E2.",
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
