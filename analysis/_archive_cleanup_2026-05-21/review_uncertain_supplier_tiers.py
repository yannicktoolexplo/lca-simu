#!/usr/bin/env python3
"""Review supplier-tier assignments initially marked as confidence=review."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IN_SUPPLIERS = ROOT / "analysis" / "output8_GEO_meaningful_supplier_tiers.csv"
OUT_REVIEW = ROOT / "analysis" / "output8_GEO_reviewed_uncertain_supplier_tiers.csv"
OUT_SOURCES = ROOT / "analysis" / "output8_GEO_reviewed_uncertain_supplier_sources.csv"
OUT_MD = ROOT / "analysis" / "output8_GEO_reviewed_uncertain_supplier_tiers.md"


def src(source_id: str, entity: str, url: str, source_type: str, note: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "entity": entity,
        "url": url,
        "source_type": source_type,
        "note": note,
    }


SOURCES = [
    src("SRC_FRN-8C9D165AC08887_WEF_001", "FRN-8C9D165AC08887", "https://sources.invalid/FRN-8C9D165AC08887/9d4a4cc13f4be79c", "institutional_profile", "FRN-8C9D165AC08887 is a large Chinese chemical corporation; good enough to validate chemical upstream role, not site traceability."),
    src("SRC_ORBIA_001", "FRN-0470CB8E24F90C", "https://sources.invalid/FRN-0470CB8E24F90C/6044e4ac7a26ae4f", "official_company", "Orbia is the current group name for FRN-DA064DA90071AA; validates chemicals/materials role."),
    src("SRC_FRN-CEF93150EAB259_001", "FRN-CEF93150EAB259", "https://sources.invalid/FRN-CEF93150EAB259/409ccae052772cab", "official_company", "FRN-CEF93150EAB259 is a petrochemical/materials producer; valid only for polymer/chemical records, not steel records."),
    src("SRC_FRN-4D555DCD74FE33_001", "FRN-4D555DCD74FE33", "https://sources.invalid/FRN-4D555DCD74FE33/b6a8ccc8390a9e31", "official_company", "FRN-4D555DCD74FE33 serves aerospace materials/chemicals; valid for chemical/composite records, not stainless steel records."),
    src("SRC_FRN-D227736E23A53A_001", "FRN-D227736E23A53A", "https://sources.invalid/FRN-D227736E23A53A/e24b8431b82fcb1e", "official_company", "FRN-D227736E23A53A is a paper and packaging materials company; validates paper upstream role."),
    src("SRC_GASCOGNE_001", "FRN-BC96F516F6356A", "https://sources.invalid/FRN-BC96F516F6356A/1a79e97f1574adc6", "official_company", "FRN-BC96F516F6356A is a paper producer; validates paper upstream role."),
    src("SRC_FRN-482DAF5037232F_001", "FRN-482DAF5037232F", "https://sources.invalid/FRN-482DAF5037232F/de7938c1aa65fe17", "official_company", "FRN-482DAF5037232F is a Brazilian paper/pulp/packaging producer."),
    src("SRC_HALCYON_001", "FRN-187C7FDD60E1BB", "https://sources.invalid/FRN-187C7FDD60E1BB/651d85ea9c43b322", "official_company", "FRN-187C7FDD60E1BB operates natural-rubber processing; validates Hevecam/PT Remco/SDCI rubber upstream roles."),
    src("SRC_FRN-26DEDB3523ED49_001", "FRN-26DEDB3523ED49", "https://sources.invalid/FRN-26DEDB3523ED49/aefc2b8c4ec6187e", "official_company", "FRN-26DEDB3523ED49 has rubber plantation/processing activities; validates LAC/Okomu/SRC rubber upstream roles."),
    src("SRC_SHANDONG_LOYAL_001", "FRN-84F9163EC3A900", "https://sources.invalid/FRN-84F9163EC3A900/0a7d9b5a8d847bdd", "official_company", "Chemical/PVC additives supplier; source quality to be checked before stress-test use."),
    src("SRC_HUDDERSFIELD_001", "FRN-0CA3DB5897A052", "https://sources.invalid/FRN-0CA3DB5897A052/5364bf02a1bbcc9d", "official_company", "UK textile/cloth supplier; validates textile transformation role."),
    src("SRC_FRN-00E06DCA30233C_001", "FRN-00E06DCA30233C", "https://sources.invalid/FRN-00E06DCA30233C/31d8719cba430090", "official_company", "Portuguese textile company; validates textile role."),
    src("SRC_MASTROTTO_001", "FRN-0D637C05CC81D5", "https://sources.invalid/FRN-0D637C05CC81D5/eb4279a904b9da5c", "official_company", "Leather group/tannery; validates leather transformation role."),
    src("SRC_SAINTGOBAIN_001", "FRN-77A20D424743A6", "https://sources.invalid/FRN-77A20D424743A6/666e062ac8887e95", "official_company", "Materials group; aerospace/silicone-specific use still needs product traceability."),
    src("SRC_FRN-87FB5EDE498059_001", "FRN-87FB5EDE498059", "https://sources.invalid/FRN-87FB5EDE498059/3afc73de1f4578b0", "official_company", "FRN-87FB5EDE498059 aerospace adhesives validate adhesive/film/composite tier role."),
    src("SRC_SHINETSU_001", "FRN-332F92E4BA4B00", "https://sources.invalid/FRN-332F92E4BA4B00/a4136b8f5d0bd7db", "official_company", "Corrects FRN-1E191B6E8030DB to Shin-Etsu for silicone materials."),
    src("SRC_DAIO_001", "FRN-B7600B824E7BC7", "https://sources.invalid/FRN-B7600B824E7BC7/6d2d8107382f8bcc", "official_company", "Japanese paper producer; validates paper role."),
    src("SRC_FRN-446E35B7988374_001", "FRN-446E35B7988374", "https://sources.invalid/FRN-446E35B7988374/f5f6bcfb08a772a0", "official_company", "Laminate/surface materials company."),
    src("SRC_FRN-D5AC44A74AFB92_001", "FRN-D5AC44A74AFB92", "https://sources.invalid/FRN-D5AC44A74AFB92/2b25512ab05af045", "official_company", "Wood-based laminate/panel producer; not aerospace-specific."),
    src("SRC_SMURFIT_001", "FRN-52D7A4109CB90E", "https://sources.invalid/FRN-52D7A4109CB90E/aaee21563a479cb9", "official_company", "Paper/packaging group; should usually be packaging/auxiliary unless paper material is deliberate."),
    src("SRC_FRN-68DAD6BBF1BAEB_001", "FRN-68DAD6BBF1BAEB", "https://sources.invalid/FRN-68DAD6BBF1BAEB/883f81d310ebce1d", "official_company", "Synthetic high-performance fabrics; plausible for leather-like upholstery."),
    src("SRC_FRN-86B55CBC7AFCE9_001", "FRN-86B55CBC7AFCE9", "https://sources.invalid/FRN-86B55CBC7AFCE9/39372132c06dbb9f", "official_company", "KYDEX thermoplastic sheet for aviation/aerospace."),
    src("SRC_FRN-E44BD8109B6A57_001", "FRN-E44BD8109B6A57", "https://sources.invalid/FRN-E44BD8109B6A57/286b5c24e12aa0e9", "official_company", "Textile company; validate textile role, not necessarily qualified aerospace site."),
    src("SRC_FRN-664F9D3A953246_001", "FRN-664F9D3A953246", "https://sources.invalid/FRN-664F9D3A953246/dd93adf35fbdb772", "official_company", "Plastics/thermoforming supplier; validates T2 plastic transformation."),
    src("SRC_LELIEVRE_001", "FRN-4D05106737BED8", "https://sources.invalid/FRN-4D05106737BED8/0c789a0c471d9e90", "official_company", "Upholstery textile/fabric supplier."),
    src("SRC_FRN-935B8529CE61B4_001", "FRN-935B8529CE61B4", "https://sources.invalid/FRN-935B8529CE61B4/fd72681fc0e04535", "official_company", "Leather supplier/distributor; plausible leather source but not aerospace qualified by this source."),
    src("SRC_FRN-BDE3FD68E4E87F_001", "FRN-BDE3FD68E4E87F", "https://sources.invalid/FRN-BDE3FD68E4E87F/8c9900b4ae3c7970", "official_company", "Silicone rubber material producer."),
    src("SRC_FRN-931CE9F49D95CD_001", "FRN-223F605AA04BC4", "https://sources.invalid/FRN-223F605AA04BC4/50b3aded68dc02dd", "official_company", "Aerospace adhesives/materials; use only with product traceability."),
    src("SRC_DIODES_001", "FRN-A75319B66652B8", "https://sources.invalid/FRN-A75319B66652B8/457b90d5d3667cac", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_FRN-3B63EA5F42EF36_001", "FRN-3B63EA5F42EF36", "https://sources.invalid/FRN-3B63EA5F42EF36/a18c45a717e0a1f8", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_FRN-498413D6464206_001", "FRN-498413D6464206", "https://sources.invalid/FRN-498413D6464206/0e0d4cceb6fcf9a4", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_FRN-5BF789044ED6FF_001", "Intel", "https://sources.invalid/FRN-5BF789044ED6FF/e4e19872dedc69fd", "official_company", "Semiconductor company; too generic without exact electronic BOM."),
    src("SRC_FRN-8DD799E0AA036C_001", "FRN-8DD799E0AA036C", "https://sources.invalid/FRN-8DD799E0AA036C/c15694cb47ee4fd9", "official_company", "Semiconductor/computing company; too generic without exact electronic BOM."),
    src("SRC_FRN-A00FD04291B8DD_001", "FRN-A00FD04291B8DD", "https://sources.invalid/FRN-A00FD04291B8DD/24891b38ebac5c21", "official_company", "Semiconductor foundry; too generic without exact electronic BOM."),
    src("SRC_FRN-A982B812225B13_001", "FRN-A982B812225B13", "https://sources.invalid/FRN-A982B812225B13/a0b38332777c93da", "official_company", "Paper/packaging group; normally packaging/auxiliary unless paper material is deliberate."),
    src("SRC_FRN-095262A67F7661_001", "FRN-095262A67F7661", "https://sources.invalid/FRN-095262A67F7661/93a75aee47536d48", "official_company", "Engineered materials/nonwovens; plausible paper/nonwoven supplier."),
    src("SRC_FRN-69EC9F91F7F98F_001", "FRN-69EC9F91F7F98F", "https://sources.invalid/FRN-69EC9F91F7F98F/cf307b14709dcfb6", "official_company", "Advanced composites/carbon fiber supplier for aerospace."),
    src("SRC_FRN-099010FD9764F4_001", "FRN-099010FD9764F4", "https://sources.invalid/FRN-099010FD9764F4/4267e1ba05f087ba", "official_company", "Aerospace adhesives/sealants; product traceability still needed."),
    src("SRC_AUBERON_001", "FRN-BF6DDA7768754E", "https://sources.invalid/FRN-BF6DDA7768754E/dc38d770264e6ecd", "official_company", "Professional display/optoelectronic systems supplier; plausible display/IFE T2."),
    src("SRC_FRN-EAF03ECECB6231_001", "FRN-EAF03ECECB6231", "https://sources.invalid/FRN-EAF03ECECB6231/e795ff9cfe57aca5", "official_company", "Optical/display technology supplier; plausible display/IFE T2."),
    src("SRC_FRN-DE6523078882AF_001", "FRN-3E0918AEFE7AA2", "https://sources.invalid/FRN-3E0918AEFE7AA2/7b4607b9efefdd19", "official_company", "Aerospace/avionics group; plausible T1/T2 for IFE/electronics."),
    src("SRC_FRN-CA06FA01372D3A_001", "FRN-CA06FA01372D3A", "https://sources.invalid/FRN-CA06FA01372D3A/e332192723aad5bd", "official_company", "Aerospace adhesive films/decoration supplier."),
    src("SRC_FRN-AB3EB7C0CECDE9_001", "FRN-A11855A23B3277", "https://sources.invalid/FRN-A11855A23B3277/bc8ed9028be3c98e", "official_company", "Aerospace systems/electronics group; exact component needed."),
    src("SRC_FRN-52D5AE23024E5C_001", "FRN-42EDB7DB79E4B3", "https://sources.invalid/FRN-42EDB7DB79E4B3/4bb47925bbd7bd27", "official_company", "Aerospace systems supplier."),
    src("SRC_FRN-9A1259AF62E7E2_001", "FRN-8D803DB4CA43C4", "https://sources.invalid/FRN-8D803DB4CA43C4/9cc25908ba459658", "official_company", "Aviation lighting/glass systems supplier."),
    src("SRC_TE_001", "FRN-2B32314A8C4A0F", "https://sources.invalid/FRN-B9C4C86C42C8B4/43e1f43c29b50066", "official_company", "Tyco Electronics should normalize to FRN-B9C4C86C42C8B4 for aerospace connectors."),
    src("SRC_MADEL_EC_001", "FRN-9039B0A26EAA3B", "https://sources.invalid/FRN-9039B0A26EAA3B/72ca9cb64e3eb91b", "official_company", "French aerospace electrical/electronic supplier; exact product needed."),
    src("SRC_KEMKO_001", "FRN-EFD76ECB77D7DC", "https://sources.invalid/FRN-EFD76ECB77D7DC/24684e2d793b48e6", "official_company", "Aerospace hardware/systems supplier; exact product needed."),
]


def decision(
    status: str,
    recommended_tier: str,
    action: str,
    reviewed_confidence: str,
    rationale: str,
    source_ids: str = "",
    canonical_supplier: str = "",
) -> dict[str, str]:
    return {
        "review_status": status,
        "recommended_tier_code": recommended_tier,
        "reviewed_action": action,
        "reviewed_confidence": reviewed_confidence,
        "review_rationale": rationale,
        "review_source_ids": source_ids,
        "canonical_supplier": canonical_supplier,
    }


D: dict[str, dict[str, str]] = {
    "FRN-8C9D165AC08887": decision("validated_supplier", "T4", "keep", "medium", "Real chemical group; keep only for polymer/rubber/chemical records.", "SRC_FRN-8C9D165AC08887_WEF_001", "FRN-8C9D165AC08887"),
    "FRN-DA064DA90071AA": decision("validated_supplier", "T4", "normalize_name", "high", "FRN-DA064DA90071AA is now Orbia; valid chemical/materials upstream supplier.", "SRC_ORBIA_001", "FRN-0470CB8E24F90C"),
    "FRN-4C5D687CCB33A2": decision("validated_supplier", "T4", "keep_with_source_check", "medium", "Plausible chemical/PVC additive supplier; keep for polymer records but verify site and product.", "SRC_SHANDONG_LOYAL_001", "FRN-4C5D687CCB33A2"),
    "Polymère": decision("generic_placeholder", "T4", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier. Replace with named polymer producer from purchasing/BOM."),
    "Aluminium": decision("generic_placeholder", "T4", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier. Replace with FRN-34B2AC7037114C/FRN-191F6AC0669F77/FRN-7A25E45203FCC9/FRN-798BE9ED657B85/etc. according to traceability."),
    "FRN-CEF93150EAB259": decision("validated_supplier_with_component_scope_issue", "T4", "keep_only_for_polymer_records", "high", "Valid chemical/polymer producer, but not valid for steel records such as 35NC6.", "SRC_FRN-CEF93150EAB259_001", "FRN-CEF93150EAB259"),
    "FRN-06F929E14E50CD": decision("validated_supplier", "T4", "normalize_name", "high", "FRN-D227736E23A53A is a paper/material supplier; keep as upstream paper source for AIRVOLT-like material.", "SRC_FRN-D227736E23A53A_001", "FRN-D227736E23A53A"),
    "FRN-BC96F516F6356A": decision("validated_supplier", "T4", "keep", "high", "Paper producer; valid upstream paper source for AIRVOLT-like material.", "SRC_GASCOGNE_001", "FRN-BC96F516F6356A"),
    "FRN-B6625637884109": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-187C7FDD60E1BB rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "FRN-B6625637884109"),
    "FRN-A561D8E52E28DD": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-187C7FDD60E1BB rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "FRN-A561D8E52E28DD"),
    "FRN-6593B612CCC15F": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-187C7FDD60E1BB rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "FRN-6593B612CCC15F"),
    "FRN-482DAF5037232F": decision("validated_supplier", "T4", "keep", "high", "Pulp/paper/packaging producer; valid paper upstream source.", "SRC_FRN-482DAF5037232F_001", "FRN-482DAF5037232F"),
    "FRN-4674144B3134A7": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-26DEDB3523ED49 rubber activity; valid upstream natural rubber source.", "SRC_FRN-26DEDB3523ED49_001", "FRN-4674144B3134A7"),
    "FRN-4E9DE984AC7CCA": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-26DEDB3523ED49 rubber activity; valid upstream natural rubber source.", "SRC_FRN-26DEDB3523ED49_001", "FRN-4E9DE984AC7CCA"),
    "FRN-4E9DE984AC7CCA Nigeria": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-26DEDB3523ED49 rubber activity; valid upstream natural rubber source.", "SRC_FRN-26DEDB3523ED49_001", "FRN-4E9DE984AC7CCA Nigeria"),
    "FRN-7BD747E6CC4CD5": decision("validated_supplier", "T4", "keep", "medium_high", "FRN-26DEDB3523ED49 rubber activity; valid upstream natural rubber source.", "SRC_FRN-26DEDB3523ED49_001", "FRN-7BD747E6CC4CD5"),
    "FRN-4D555DCD74FE33": decision("validated_supplier_with_component_scope_issue", "T4", "keep_only_for_chemical_or_composite_records", "high", "Valid aerospace chemical/materials supplier, but not valid for stainless steel records.", "SRC_FRN-4D555DCD74FE33_001", "FRN-4D555DCD74FE33"),
    "FRN-D9805DB47110D5": decision("validated_supplier", "T3", "normalize_name", "high", "Textile supplier; valid textile transformation node.", "SRC_HUDDERSFIELD_001", "FRN-0CA3DB5897A052"),
    "FRN-BF4B1E88874E39": decision("needs_business_validation", "T3", "verify_exact_legal_entity_and_site", "low", "Name is plausible but source/country linkage was not robust enough; keep only after purchasing validation."),
    "FRN-01464643EEA78E": decision("validated_supplier", "T3", "keep", "medium", "Plausible velvet/textile supplier; keep but confirm actual aerospace/seat material source.", "", "FRN-01464643EEA78E"),
    "FRN-00E06DCA30233C": decision("validated_supplier", "T3", "keep", "high", "Portuguese textile company; valid textile transformation node.", "SRC_FRN-00E06DCA30233C_001", "FRN-00E06DCA30233C"),
    "FRN-093719BF852626": decision("needs_business_validation", "T3", "verify_exact_legal_entity_and_site", "low", "Plausible textile supplier but not sufficiently sourced; validate before using as switch option."),
    "Velours": decision("generic_placeholder", "T3", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier."),
    "FRN-1318E9740D89D0": decision("validated_supplier", "T3", "normalize_name", "high", "Leather group/tannery; valid leather transformation source.", "SRC_MASTROTTO_001", "FRN-0D637C05CC81D5"),
    "FRN-E857FD00FA3A46": decision("industry_association_not_supplier", "T3", "remove_from_supplier_network", "high", "Industry association/channel, useful for sourcing context but not a supplier node.", "SRC_FRN-935B8529CE61B4_001", ""),
    "FRN-77A20D424743A6": decision("validated_supplier", "T3", "keep_with_product_scope_check", "medium_high", "Materials group; valid only if linked to a specific silicone/glass/material product.", "SRC_SAINTGOBAIN_001", "FRN-77A20D424743A6"),
    "FRN-87FB5EDE498059": decision("validated_supplier", "T3", "keep", "high", "Aerospace adhesives/materials supplier.", "SRC_FRN-87FB5EDE498059_001", "FRN-87FB5EDE498059"),
    "FRN-C8F1EAD07EF6EA": decision("generic_placeholder", "T3", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier."),
    "FRN-1E191B6E8030DB": decision("validated_supplier", "T3", "normalize_name", "high", "Correct to FRN-332F92E4BA4B00 for silicone material; Toshiba part is likely a typo/noise.", "SRC_SHINETSU_001", "FRN-332F92E4BA4B00"),
    "FRN-B7600B824E7BC7": decision("validated_supplier", "T3", "keep", "high", "Paper producer; valid paper transformation/upstream node.", "SRC_DAIO_001", "FRN-B7600B824E7BC7"),
    "FRN-F05E300AE66407": decision("validated_supplier", "T3", "keep_with_aerospace_scope_check", "medium", "Epoxy/resin supplier; validate aerospace grade and product before simulation.", "SRC_FRN-446E35B7988374_001", "FRN-F05E300AE66407"),
    "FRN-446E35B7988374": decision("validated_supplier", "T3", "keep", "medium_high", "Laminate/surface material producer; plausible for laminate materials.", "SRC_FRN-446E35B7988374_001", "FRN-446E35B7988374"),
    "FRN-D5AC44A74AFB92": decision("validated_supplier_with_scope_issue", "T3", "keep_with_scope_check", "medium", "Laminate/panel producer; not aerospace-specific, validate material relevance.", "SRC_FRN-D5AC44A74AFB92_001", "FRN-D5AC44A74AFB92"),
    "FRN-7D06930B422A10": decision("packaging_or_paper_auxiliary", "PKG", "move_to_packaging_or_auxiliary_flow", "high", "Packaging/paper group; not a manufacturing tier unless the paper itself is part of material.", "SRC_SMURFIT_001", "FRN-52D7A4109CB90E"),
    "FRN-68DAD6BBF1BAEB": decision("validated_supplier", "T3", "normalize_name", "high", "Synthetic high-performance fabric/leather-like material supplier.", "SRC_FRN-68DAD6BBF1BAEB_001", "FRN-68DAD6BBF1BAEB"),
    "FRN-0D8AFB8AB6CBCA": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_product", "low", "Supplier name is too weakly sourced for stress-test use."),
    "FRN-A98036B11DAF17": decision("validated_supplier", "T2", "normalize_name", "medium_high", "Display/optoelectronic systems supplier; plausible T2 for screen/display records.", "SRC_AUBERON_001", "FRN-BF6DDA7768754E"),
    "FRN-EAF03ECECB6231": decision("validated_supplier", "T2", "keep", "medium_high", "Optical/display technology supplier; plausible T2 for display records.", "SRC_FRN-EAF03ECECB6231_001", "FRN-EAF03ECECB6231"),
    "FRN-664F9D3A953246": decision("validated_supplier", "T2", "keep", "medium_high", "Plastics/thermoforming supplier; valid T2 transformation.", "SRC_FRN-664F9D3A953246_001", "FRN-664F9D3A953246"),
    "FRN-31EADBF3BC3F5D": decision("validated_supplier", "T2", "normalize_name", "high", "Upholstery textile supplier; valid textile source, but aerospace qualification to verify.", "SRC_LELIEVRE_001", "FRN-4D05106737BED8"),
    "FRN-EF424F32D1E80A": decision("validated_supplier", "T2", "normalize_name", "high", "FRN-86B55CBC7AFCE9 is directly relevant for aviation/aerospace thermoplastic sheet.", "SRC_FRN-86B55CBC7AFCE9_001", "FRN-86B55CBC7AFCE9"),
    "FRN-E44BD8109B6A57": decision("validated_supplier", "T2", "keep_with_aerospace_scope_check", "medium_high", "Textile supplier; validate actual seat program material.", "SRC_FRN-E44BD8109B6A57_001", "FRN-E44BD8109B6A57"),
    "FRN-727BE76F9CE12D": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_site", "low", "Could not robustly validate as industrial seat/leather supplier."),
    "FRN-935B8529CE61B4": decision("validated_supplier_with_scope_issue", "T2", "keep_as_leather_distributor_if_traceable", "medium", "Leather supplier/distributor, not an aerospace-qualified supplier by available source.", "SRC_FRN-935B8529CE61B4_001", "FRN-935B8529CE61B4"),
    "FRN-002EAED5EB16E6": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_part_supplier_or_distributor", "medium", "Real electronics brand, but too generic as supply node; use exact display part supplier/distributor."),
    "FRN-7A1F937DE08462": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_site", "low", "Name too ambiguous; could be composite supplier but source was not robust."),
    "FRN-98FB52FC24BF7A": decision("wrong_scope_or_unrelated", "T2", "remove_unless_product_traceability_exists", "low", "Industrial valve group; not coherent for listed plastics/resin/leather records without product proof."),
    "Auger": decision("needs_business_validation", "T2", "verify_exact_supplier", "low", "Ambiguous supplier name; do not use for switches before validation."),
    "FRN-DA7F97DC1B47FC": decision("legacy_or_defunct_supplier", "T2", "replace_with_current_legal_entity", "medium", "Legacy chemical name; replace with current group/product source such as FRN-4D555DCD74FE33/Rhodia if applicable."),
    "FRN-8694A96AFD62DA": decision("validated_supplier", "T2", "normalize_name", "high", "FRN-BDE3FD68E4E87F is a silicone rubber material supplier.", "SRC_FRN-BDE3FD68E4E87F_001", "FRN-BDE3FD68E4E87F"),
    "3M": decision("validated_supplier_with_scope_issue", "T2", "keep_only_with_product_traceability", "high", "FRN-223F605AA04BC4 is valid, but exact material/product should be linked.", "SRC_FRN-931CE9F49D95CD_001", "3M"),
    "FRN-39CD26763E8365": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_product", "low", "Ambiguous electronics supplier; do not use as switch before validation."),
    "FRN-0A6EA63B8561C3": decision("wrong_scope_or_unrelated", "T2", "remove_unless_material_traceability_exists", "low", "Laminate flooring brand; not a credible aerospace-seat supplier without material traceability."),
    "FRN-A75319B66652B8": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics, not direct aerospace supplier.", "SRC_DIODES_001", "FRN-A75319B66652B8"),
    "FRN-095262A67F7661": decision("validated_supplier", "T2", "keep_with_material_scope_check", "medium_high", "Engineered materials/nonwovens supplier; plausible for paper/nonwoven material.", "SRC_FRN-095262A67F7661_001", "FRN-095262A67F7661"),
    "FRN-29ACA449A1250E": decision("packaging_or_paper_auxiliary", "PKG", "move_to_packaging_or_auxiliary_flow", "high", "Paper/packaging group; usually packaging/auxiliary unless material paper is deliberate.", "SRC_FRN-A982B812225B13_001", "FRN-A982B812225B13"),
    "FRN-759A8104A86D5D": decision("validated_supplier", "T2", "keep_or_reclassify_T3_composites", "high", "Aerospace composites/carbon fiber supplier.", "SRC_FRN-69EC9F91F7F98F_001", "FRN-69EC9F91F7F98F"),
    "FRN-6C91A924791F76": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics but not direct seat supplier.", "SRC_FRN-3B63EA5F42EF36_001", "FRN-3B63EA5F42EF36"),
    "Intel --> fondée en 1968 qui est le deuxième fabricant mondial de semi-conducteurs.": decision("cots_brand_not_supply_node", "T2", "normalize_or_remove", "medium", "Text contains encyclopedia note; if kept, normalize to Intel and model only as generic semiconductor upstream.", "SRC_FRN-5BF789044ED6FF_001", "Intel"),
    "FRN-8DD799E0AA036C": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_component_supplier", "medium", "Too generic without exact electronic BOM.", "SRC_FRN-8DD799E0AA036C_001", "FRN-8DD799E0AA036C"),
    "FRN-045ADA837ADDB0": decision("wrong_scope_or_unrelated", "T2", "remove_unless_material_traceability_exists", "low", "Flooring laminate brand; not credible as aerospace-seat supply node without traceability."),
    "FRN-04891ED2B9AC0F": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics but not direct seat supplier.", "SRC_FRN-498413D6464206_001", "FRN-498413D6464206"),
    "FRN-D07D31613908BE": decision("wrong_scope_or_unrelated", "T2", "remove_unless_product_traceability_exists", "low", "Data logger/vehicle testing supplier does not fit cable bracket record without exact product proof."),
    "FRN-AEA0242468D6C5": decision("validated_supplier", "T2", "keep_or_reclassify_T3_composites", "high", "Carbon/composites materials supplier.", "SRC_FRN-69EC9F91F7F98F_001", "FRN-AEA0242468D6C5"),
    "FRN-099010FD9764F4": decision("validated_supplier", "T2", "keep_with_product_scope_check", "high", "Aerospace adhesives/sealants supplier; verify exact adhesive/film product.", "SRC_FRN-099010FD9764F4_001", "FRN-099010FD9764F4"),
    "FRN-A00FD04291B8DD": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_component_supplier", "medium", "Foundry too far upstream/generic without exact electronic BOM.", "SRC_FRN-A00FD04291B8DD_001", "FRN-A00FD04291B8DD"),
    "FRN-DE6523078882AF": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "Aerospace/avionics supplier; plausible T1/T2 for IFE/electronics.", "SRC_FRN-DE6523078882AF_001", "FRN-DE6523078882AF"),
    "FRN-E8268BC81624C2": decision("not_verified_probable_error", "T1", "remove_or_replace_with_JAMCO_if_intended", "low", "Not verifiable as aerospace-seat supplier; likely typo/noise."),
    "Continental": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_display_supplier", "medium", "Real electronics/automotive group but not a qualified aerospace seat supplier by current data."),
    "FRN-1BDCFA9C2C8341": decision("wrong_scope_or_too_broad", "T1", "remove_unless_exact_GE_aerospace_product", "medium", "Too broad and mismatched for silicone/cables without product traceability."),
    "FRN-F2989334E97912": decision("needs_business_validation", "T1", "verify_exact_legal_entity_and_product", "low", "Ambiguous supplier name."),
    "FRN-B18137D5260D41": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_product", "medium", "Automotive electronics brand; not a direct aerospace-seat supplier without proof."),
    "FRN-CA06FA01372D3A": decision("validated_supplier", "T1", "keep", "high", "Aerospace adhesive films/decoration supplier.", "SRC_FRN-CA06FA01372D3A_001", "FRN-CA06FA01372D3A"),
    "FRN-45A091671294B0": decision("duplicate_normalization", "T1", "merge_with_ESPACE", "medium", "Duplicate naming variant; merge into existing FRN-45A091671294B0 supplier record."),
    "FRN-AB3EB7C0CECDE9": decision("validated_supplier_with_scope_issue", "T1", "keep_with_product_scope_check", "high", "Aerospace systems/electronics group; exact cable/electronic product still needed.", "SRC_FRN-AB3EB7C0CECDE9_001", "FRN-A11855A23B3277"),
    "FRN-EFD76ECB77D7DC": decision("validated_supplier", "T1", "keep_with_product_scope_check", "medium_high", "Aerospace supplier; exact product/site should be validated.", "SRC_KEMKO_001", "FRN-EFD76ECB77D7DC"),
    "FRN-52D5AE23024E5C": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "Aerospace systems supplier; exact ECU/actuation relevance should be validated.", "SRC_FRN-52D5AE23024E5C_001", "FRN-42EDB7DB79E4B3"),
    "FRN-9039B0A26EAA3B": decision("validated_supplier", "T1", "keep", "medium_high", "French aerospace electrical/electronic supplier.", "SRC_MADEL_EC_001", "FRN-9039B0A26EAA3B"),
    "FRN-58617EE9251D1E": decision("needs_business_validation", "T1", "verify_exact_legal_entity_and_product", "low", "Ambiguous supplier name."),
    "FRN-CF3EA93B7C15EE": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_part", "medium", "Likely FRN-CF3EA93B7C15EE Electric; too generic as T1 cable supplier."),
    "FRN-9A1259AF62E7E2": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "FRN-9A1259AF62E7E2 has aviation markets; plausible lighting/glass supplier.", "SRC_FRN-9A1259AF62E7E2_001", "FRN-8D803DB4CA43C4"),
    "FRN-338328B0A1AC92": decision("validated_supplier", "T1", "normalize_name", "high", "Normalize to FRN-B9C4C86C42C8B4; aerospace connectors/electronics supplier.", "SRC_TE_001", "FRN-B9C4C86C42C8B4"),
}


def main() -> None:
    rows = list(csv.DictReader(IN_SUPPLIERS.open(encoding="utf-8-sig")))
    review_rows = [row for row in rows if row["confidence"] == "review"]
    out_rows = []
    for row in review_rows:
        item = dict(row)
        item.update(D.get(row["supplier"], decision("unreviewed", row["tier_code"], "manual_review_required", "low", "No decision rule found.")))
        out_rows.append(item)

    with OUT_SOURCES.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SOURCES[0].keys()))
        writer.writeheader()
        writer.writerows(SOURCES)

    fields = list(out_rows[0].keys())
    with OUT_REVIEW.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    status_counts = Counter(row["review_status"] for row in out_rows)
    action_counts = Counter(row["reviewed_action"] for row in out_rows)
    recommended_counts = Counter(row["recommended_tier_code"] for row in out_rows)
    high_value = sorted(out_rows, key=lambda r: float(r["mass_exposure_kg_sum_record_level"] or 0), reverse=True)[:20]
    remove_rows = [r for r in out_rows if r["review_status"] in {"generic_placeholder", "wrong_scope_or_unrelated", "not_verified_probable_error", "industry_association_not_supplier"}]
    lines = [
        "# Review of uncertain supplier tiers",
        "",
        f"- Input: `{IN_SUPPLIERS.as_posix()}`",
        f"- Reviewed rows: `{OUT_REVIEW.as_posix()}`",
        f"- Source registry: `{OUT_SOURCES.as_posix()}`",
        "",
        "## Summary",
        "",
        f"- Rows reviewed: {len(out_rows)}",
        "- Review status: " + ", ".join(f"{k}={v}" for k, v in status_counts.most_common()),
        "- Recommended tier/action target: " + ", ".join(f"{k}={v}" for k, v in recommended_counts.most_common()),
        "- Actions: " + ", ".join(f"{k}={v}" for k, v in action_counts.most_common()),
        "",
        "## Main decisions",
        "",
        "- Keep validated real suppliers, but attach scope notes when the supplier is real yet not valid for every component row.",
        "- Remove generic placeholders such as `Polymere`, `Aluminium`, `Velours`, `FRN-C8F1EAD07EF6EA` from the supplier network.",
        "- Move paper/packaging groups such as FRN-A982B812225B13 or FRN-52D7A4109CB90E to packaging/auxiliary unless the paper is explicitly part of the seat material.",
        "- Demote generic electronics brands/foundries to COTS-upstream context unless an exact part supplier is known.",
        "- Normalize noisy names: `FRN-DA064DA90071AA -> Orbia`, `FRN-1E191B6E8030DB -> FRN-332F92E4BA4B00`, `FRN-338328B0A1AC92 -> FRN-B9C4C86C42C8B4`, `Sekisui SPI -> FRN-86B55CBC7AFCE9`.",
        "",
        "## Remove / replace first",
        "",
    ]
    for row in remove_rows:
        lines.append(f"- {row['tier_code']} `{row['supplier']}`: {row['review_status']} - {row['review_rationale']}")
    lines += [
        "",
        "## Highest exposure reviewed rows",
        "",
    ]
    for row in high_value:
        lines.append(
            f"- {row['tier_code']} `{row['supplier']}` -> {row['recommended_tier_code']}, "
            f"status={row['review_status']}, exposure={row['mass_exposure_kg_sum_record_level']} kg, action={row['reviewed_action']}"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] wrote {OUT_REVIEW}")
    print(f"[OK] wrote {OUT_SOURCES}")
    print(f"[OK] wrote {OUT_MD}")
    print(f"[INFO] reviewed={len(out_rows)} statuses={dict(status_counts)}")


if __name__ == "__main__":
    main()
