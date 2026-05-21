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
    src("SRC_CHEMCHINA_WEF_001", "ChemChina", "https://www.weforum.org/organizations/china-national-chemical-corporation-chemchina/", "institutional_profile", "ChemChina is a large Chinese chemical corporation; good enough to validate chemical upstream role, not site traceability."),
    src("SRC_ORBIA_001", "Orbia / Mexichem", "https://www.orbia.com/this-is-orbia/who-we-are/", "official_company", "Orbia is the current group name for Mexichem; validates chemicals/materials role."),
    src("SRC_SABIC_001", "SABIC", "https://www.sabic.com/en/about", "official_company", "SABIC is a petrochemical/materials producer; valid only for polymer/chemical records, not steel records."),
    src("SRC_SOLVAY_001", "Solvay", "https://www.solvay.com/en/solutions-market/aerospace", "official_company", "Solvay serves aerospace materials/chemicals; valid for chemical/composite records, not stainless steel records."),
    src("SRC_BILLERUD_001", "Billerud", "https://www.billerud.com/about-us", "official_company", "Billerud is a paper and packaging materials company; validates paper upstream role."),
    src("SRC_GASCOGNE_001", "Gascogne Papier", "https://www.gascognepapier.com/en/", "official_company", "Gascogne Papier is a paper producer; validates paper upstream role."),
    src("SRC_KLABIN_001", "Klabin", "https://klabin.com.br/en/about-klabin", "official_company", "Klabin is a Brazilian paper/pulp/packaging producer."),
    src("SRC_HALCYON_001", "Halcyon Agri", "https://www.halcyonagri.com/our-business/processing/", "official_company", "Halcyon Agri operates natural-rubber processing; validates Hevecam/PT Remco/SDCI rubber upstream roles."),
    src("SRC_SOCFIN_001", "Socfin", "https://www.socfin.com/en/activities/rubber", "official_company", "Socfin has rubber plantation/processing activities; validates LAC/Okomu/SRC rubber upstream roles."),
    src("SRC_SHANDONG_LOYAL_001", "Shandong Loyal Chemical", "https://www.loyalchem.com/", "official_company", "Chemical/PVC additives supplier; source quality to be checked before stress-test use."),
    src("SRC_HUDDERSFIELD_001", "Huddersfield Textiles", "https://www.huddersfieldtextiles.com/", "official_company", "UK textile/cloth supplier; validates textile transformation role."),
    src("SRC_SOMANI_001", "Somani", "https://www.somani.pt/en/", "official_company", "Portuguese textile company; validates textile role."),
    src("SRC_MASTROTTO_001", "Gruppo Mastrotto", "https://www.mastrotto.com/en/", "official_company", "Leather group/tannery; validates leather transformation role."),
    src("SRC_SAINTGOBAIN_001", "Saint-Gobain", "https://www.saint-gobain.com/en", "official_company", "Materials group; aerospace/silicone-specific use still needs product traceability."),
    src("SRC_HENKEL_001", "Henkel", "https://www.henkel-adhesives.com/us/en/industries/aerospace.html", "official_company", "Henkel aerospace adhesives validate adhesive/film/composite tier role."),
    src("SRC_SHINETSU_001", "Shin-Etsu Silicones", "https://www.shinetsusilicone-global.com/", "official_company", "Corrects Toschiba-Shinetsu to Shin-Etsu for silicone materials."),
    src("SRC_DAIO_001", "Daio Paper", "https://www.daio-paper.co.jp/en/company/", "official_company", "Japanese paper producer; validates paper role."),
    src("SRC_FORMICA_001", "Formica", "https://www.formica.com/en-us/about-us", "official_company", "Laminate/surface materials company."),
    src("SRC_KRONOTEX_001", "Kronotex", "https://www.kronotex.com/en/company/", "official_company", "Wood-based laminate/panel producer; not aerospace-specific."),
    src("SRC_SMURFIT_001", "Smurfit Kappa", "https://www.smurfitkappa.com/about", "official_company", "Paper/packaging group; should usually be packaging/auxiliary unless paper material is deliberate."),
    src("SRC_ULTRAFABRICS_001", "Ultrafabrics", "https://www.ultrafabricsinc.com/", "official_company", "Synthetic high-performance fabrics; plausible for leather-like upholstery."),
    src("SRC_SEKISUI_KYDEX_001", "SEKISUI KYDEX", "https://sekisuikydex.com/markets/aviation-aerospace/", "official_company", "KYDEX thermoplastic sheet for aviation/aerospace."),
    src("SRC_KVADRAT_001", "Kvadrat", "https://www.kvadrat.dk/en/about", "official_company", "Textile company; validate textile role, not necessarily qualified aerospace site."),
    src("SRC_PLASTIFORM_001", "Plastiform", "https://www.plastiform.fr/", "official_company", "Plastics/thermoforming supplier; validates T2 plastic transformation."),
    src("SRC_LELIEVRE_001", "Lelièvre Paris", "https://www.lelievreparis.com/en/", "official_company", "Upholstery textile/fabric supplier."),
    src("SRC_MAISON_FICHET_001", "Maison Fichet", "https://www.fichet.fr/", "official_company", "Leather supplier/distributor; plausible leather source but not aerospace qualified by this source."),
    src("SRC_SILICONE_ENGINEERING_001", "Silicone Engineering", "https://silicone.co.uk/", "official_company", "Silicone rubber material producer."),
    src("SRC_3M_001", "3M Aerospace", "https://www.3m.com/3M/en_US/aerospace-us/", "official_company", "Aerospace adhesives/materials; use only with product traceability."),
    src("SRC_DIODES_001", "Diodes Incorporated", "https://www.diodes.com/about/company-profile/", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_INFINEON_001", "Infineon", "https://www.infineon.com/cms/en/about-infineon/company/", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_ROHM_001", "ROHM", "https://www.rohm.com/company", "official_company", "Semiconductor company; COTS electronics upstream."),
    src("SRC_INTEL_001", "Intel", "https://www.intel.com/content/www/us/en/company-overview/company-overview.html", "official_company", "Semiconductor company; too generic without exact electronic BOM."),
    src("SRC_NVIDIA_001", "NVIDIA", "https://www.nvidia.com/en-us/about-nvidia/", "official_company", "Semiconductor/computing company; too generic without exact electronic BOM."),
    src("SRC_TSMC_001", "TSMC", "https://www.tsmc.com/english/aboutTSMC", "official_company", "Semiconductor foundry; too generic without exact electronic BOM."),
    src("SRC_MONDI_001", "Mondi", "https://www.mondigroup.com/about-mondi/", "official_company", "Paper/packaging group; normally packaging/auxiliary unless paper material is deliberate."),
    src("SRC_GLATFELTER_001", "Glatfelter", "https://www.glatfelter.com/about-us/", "official_company", "Engineered materials/nonwovens; plausible paper/nonwoven supplier."),
    src("SRC_HEXCEL_001", "Hexcel", "https://www.hexcel.com/About/", "official_company", "Advanced composites/carbon fiber supplier for aerospace."),
    src("SRC_SIKA_001", "Sika", "https://industry.sika.com/en/home/transportation/aerospace.html", "official_company", "Aerospace adhesives/sealants; product traceability still needed."),
    src("SRC_AUBERON_001", "Auberon Technologies", "https://auberon-technologies.com/", "official_company", "Professional display/optoelectronic systems supplier; plausible display/IFE T2."),
    src("SRC_INNOPTEC_001", "Innoptec", "https://www.innoptec.com/", "official_company", "Optical/display technology supplier; plausible display/IFE T2."),
    src("SRC_THALES_001", "Thales Aerospace", "https://www.thalesgroup.com/en/markets/aerospace", "official_company", "Aerospace/avionics group; plausible T1/T2 for IFE/electronics."),
    src("SRC_ADHETEC_001", "Adhetec", "https://www.adhetec.com/aerospace/", "official_company", "Aerospace adhesive films/decoration supplier."),
    src("SRC_HONEYWELL_001", "Honeywell Aerospace", "https://aerospace.honeywell.com/", "official_company", "Aerospace systems/electronics group; exact component needed."),
    src("SRC_LIEBHERR_001", "Liebherr Aerospace", "https://www.liebherr.com/en/int/products/aerospace-and-transportation-systems/aerospace-and-transportation-systems.html", "official_company", "Aerospace systems supplier."),
    src("SRC_SCHOTT_001", "SCHOTT Aviation", "https://www.schott.com/en-us/markets/aviation", "official_company", "Aviation lighting/glass systems supplier."),
    src("SRC_TE_001", "TE Connectivity Aerospace", "https://www.te.com/en/industries/aerospace.html", "official_company", "Tyco Electronics should normalize to TE Connectivity for aerospace connectors."),
    src("SRC_MADEL_EC_001", "Madelec Aero", "https://madelec-aero.com/", "official_company", "French aerospace electrical/electronic supplier; exact product needed."),
    src("SRC_KEMKO_001", "Kemko Aerospace", "https://kemkoaerospace.net/", "official_company", "Aerospace hardware/systems supplier; exact product needed."),
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
    "ChemChina": decision("validated_supplier", "T4", "keep", "medium", "Real chemical group; keep only for polymer/rubber/chemical records.", "SRC_CHEMCHINA_WEF_001", "ChemChina"),
    "Mexichem": decision("validated_supplier", "T4", "normalize_name", "high", "Mexichem is now Orbia; valid chemical/materials upstream supplier.", "SRC_ORBIA_001", "Orbia / Mexichem"),
    "Shandong Loyal Chemical Co., Ltd.": decision("validated_supplier", "T4", "keep_with_source_check", "medium", "Plausible chemical/PVC additive supplier; keep for polymer records but verify site and product.", "SRC_SHANDONG_LOYAL_001", "Shandong Loyal Chemical Co., Ltd."),
    "Polymère": decision("generic_placeholder", "T4", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier. Replace with named polymer producer from purchasing/BOM."),
    "Aluminium": decision("generic_placeholder", "T4", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier. Replace with Alcoa/Hindalco/Chalco/Constellium/etc. according to traceability."),
    "SABIC": decision("validated_supplier_with_component_scope_issue", "T4", "keep_only_for_polymer_records", "high", "Valid chemical/polymer producer, but not valid for steel records such as 35NC6.", "SRC_SABIC_001", "SABIC"),
    "Billerudkorsnäs": decision("validated_supplier", "T4", "normalize_name", "high", "Billerud is a paper/material supplier; keep as upstream paper source for AIRVOLT-like material.", "SRC_BILLERUD_001", "Billerud"),
    "Gascogne Papier": decision("validated_supplier", "T4", "keep", "high", "Paper producer; valid upstream paper source for AIRVOLT-like material.", "SRC_GASCOGNE_001", "Gascogne Papier"),
    "Halcyon Hevecam": decision("validated_supplier", "T4", "keep", "medium_high", "Halcyon Agri rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "Halcyon Hevecam"),
    "Halcyon PT Remco Jambi": decision("validated_supplier", "T4", "keep", "medium_high", "Halcyon Agri rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "Halcyon PT Remco Jambi"),
    "Halcyon SDCI-A": decision("validated_supplier", "T4", "keep", "medium_high", "Halcyon Agri rubber processing/subsidiary; valid upstream natural rubber source.", "SRC_HALCYON_001", "Halcyon SDCI-A"),
    "Klabin S.A.": decision("validated_supplier", "T4", "keep", "high", "Pulp/paper/packaging producer; valid paper upstream source.", "SRC_KLABIN_001", "Klabin S.A."),
    "Socfin LAC Liberia": decision("validated_supplier", "T4", "keep", "medium_high", "Socfin rubber activity; valid upstream natural rubber source.", "SRC_SOCFIN_001", "Socfin LAC Liberia"),
    "Socfin Okomu": decision("validated_supplier", "T4", "keep", "medium_high", "Socfin rubber activity; valid upstream natural rubber source.", "SRC_SOCFIN_001", "Socfin Okomu"),
    "Socfin Okomu Nigeria": decision("validated_supplier", "T4", "keep", "medium_high", "Socfin rubber activity; valid upstream natural rubber source.", "SRC_SOCFIN_001", "Socfin Okomu Nigeria"),
    "Socfin SRC Weala": decision("validated_supplier", "T4", "keep", "medium_high", "Socfin rubber activity; valid upstream natural rubber source.", "SRC_SOCFIN_001", "Socfin SRC Weala"),
    "Solvay": decision("validated_supplier_with_component_scope_issue", "T4", "keep_only_for_chemical_or_composite_records", "high", "Valid aerospace chemical/materials supplier, but not valid for stainless steel records.", "SRC_SOLVAY_001", "Solvay"),
    "Tissu Huddersfield": decision("validated_supplier", "T3", "normalize_name", "high", "Textile supplier; valid textile transformation node.", "SRC_HUDDERSFIELD_001", "Huddersfield Textiles"),
    "Paragon Textiles": decision("needs_business_validation", "T3", "verify_exact_legal_entity_and_site", "low", "Name is plausible but source/country linkage was not robust enough; keep only after purchasing validation."),
    "Yamazaki Velvet Co.": decision("validated_supplier", "T3", "keep", "medium", "Plausible velvet/textile supplier; keep but confirm actual aerospace/seat material source.", "", "Yamazaki Velvet Co."),
    "SOMANI": decision("validated_supplier", "T3", "keep", "high", "Portuguese textile company; valid textile transformation node.", "SRC_SOMANI_001", "SOMANI"),
    "Tongxiang Zhuoyi Textile": decision("needs_business_validation", "T3", "verify_exact_legal_entity_and_site", "low", "Plausible textile supplier but not sufficiently sourced; validate before using as switch option."),
    "Velours": decision("generic_placeholder", "T3", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier."),
    "Gruppo Mastrotto (Arzignano, Italie)": decision("validated_supplier", "T3", "normalize_name", "high", "Leather group/tannery; valid leather transformation source.", "SRC_MASTROTTO_001", "Gruppo Mastrotto"),
    "La Filière Française du cuir": decision("industry_association_not_supplier", "T3", "remove_from_supplier_network", "high", "Industry association/channel, useful for sourcing context but not a supplier node.", "SRC_MAISON_FICHET_001", ""),
    "Saint-Gobain": decision("validated_supplier", "T3", "keep_with_product_scope_check", "medium_high", "Materials group; valid only if linked to a specific silicone/glass/material product.", "SRC_SAINTGOBAIN_001", "Saint-Gobain"),
    "HENKEL": decision("validated_supplier", "T3", "keep", "high", "Aerospace adhesives/materials supplier.", "SRC_HENKEL_001", "Henkel"),
    "Tissus:": decision("generic_placeholder", "T3", "remove_replace_with_named_supplier", "high", "Generic material label, not a supplier."),
    "Toschiba-Shinetsu": decision("validated_supplier", "T3", "normalize_name", "high", "Correct to Shin-Etsu Silicones for silicone material; Toshiba part is likely a typo/noise.", "SRC_SHINETSU_001", "Shin-Etsu Silicones"),
    "Daio Paper Corporation": decision("validated_supplier", "T3", "keep", "high", "Paper producer; valid paper transformation/upstream node.", "SRC_DAIO_001", "Daio Paper Corporation"),
    "EPODEX": decision("validated_supplier", "T3", "keep_with_aerospace_scope_check", "medium", "Epoxy/resin supplier; validate aerospace grade and product before simulation.", "SRC_FORMICA_001", "EPODEX"),
    "FORMICA": decision("validated_supplier", "T3", "keep", "medium_high", "Laminate/surface material producer; plausible for laminate materials.", "SRC_FORMICA_001", "Formica"),
    "Kronotex GmbH & Co": decision("validated_supplier_with_scope_issue", "T3", "keep_with_scope_check", "medium", "Laminate/panel producer; not aerospace-specific, validate material relevance.", "SRC_KRONOTEX_001", "Kronotex GmbH & Co"),
    "Smurfit Kappa Group plc": decision("packaging_or_paper_auxiliary", "PKG", "move_to_packaging_or_auxiliary_flow", "high", "Packaging/paper group; not a manufacturing tier unless the paper itself is part of material.", "SRC_SMURFIT_001", "Smurfit Kappa"),
    "Ultrafabrics (Japon)": decision("validated_supplier", "T3", "normalize_name", "high", "Synthetic high-performance fabric/leather-like material supplier.", "SRC_ULTRAFABRICS_001", "Ultrafabrics"),
    "A Tech Supply APS": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_product", "low", "Supplier name is too weakly sourced for stress-test use."),
    "Auberon technologie": decision("validated_supplier", "T2", "normalize_name", "medium_high", "Display/optoelectronic systems supplier; plausible T2 for screen/display records.", "SRC_AUBERON_001", "Auberon Technologies"),
    "Innoptec": decision("validated_supplier", "T2", "keep", "medium_high", "Optical/display technology supplier; plausible T2 for display records.", "SRC_INNOPTEC_001", "Innoptec"),
    "Plastiform": decision("validated_supplier", "T2", "keep", "medium_high", "Plastics/thermoforming supplier; valid T2 transformation.", "SRC_PLASTIFORM_001", "Plastiform"),
    "Lelièvre Paris (velours)": decision("validated_supplier", "T2", "normalize_name", "high", "Upholstery textile supplier; valid textile source, but aerospace qualification to verify.", "SRC_LELIEVRE_001", "Lelièvre Paris"),
    "Sekisui SPI (Kydex)": decision("validated_supplier", "T2", "normalize_name", "high", "SEKISUI KYDEX is directly relevant for aviation/aerospace thermoplastic sheet.", "SRC_SEKISUI_KYDEX_001", "SEKISUI KYDEX"),
    "Kvadrat": decision("validated_supplier", "T2", "keep_with_aerospace_scope_check", "medium_high", "Textile supplier; validate actual seat program material.", "SRC_KVADRAT_001", "Kvadrat"),
    "EUREKA SARL DERAYGE SERVICE": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_site", "low", "Could not robustly validate as industrial seat/leather supplier."),
    "Maison Fichet": decision("validated_supplier_with_scope_issue", "T2", "keep_as_leather_distributor_if_traceable", "medium", "Leather supplier/distributor, not an aerospace-qualified supplier by available source.", "SRC_MAISON_FICHET_001", "Maison Fichet"),
    "SONY": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_part_supplier_or_distributor", "medium", "Real electronics brand, but too generic as supply node; use exact display part supplier/distributor."),
    "STECO": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_site", "low", "Name too ambiguous; could be composite supplier but source was not robust."),
    "Valco Group": decision("wrong_scope_or_unrelated", "T2", "remove_unless_product_traceability_exists", "low", "Industrial valve group; not coherent for listed plastics/resin/leather records without product proof."),
    "Auger": decision("needs_business_validation", "T2", "verify_exact_supplier", "low", "Ambiguous supplier name; do not use for switches before validation."),
    "Rhône Poulenc": decision("legacy_or_defunct_supplier", "T2", "replace_with_current_legal_entity", "medium", "Legacy chemical name; replace with current group/product source such as Solvay/Rhodia if applicable."),
    "Silicon Engineering": decision("validated_supplier", "T2", "normalize_name", "high", "Silicone Engineering is a silicone rubber material supplier.", "SRC_SILICONE_ENGINEERING_001", "Silicone Engineering"),
    "3M": decision("validated_supplier_with_scope_issue", "T2", "keep_only_with_product_traceability", "high", "3M Aerospace is valid, but exact material/product should be linked.", "SRC_3M_001", "3M"),
    "BT Electronics": decision("needs_business_validation", "T2", "verify_exact_legal_entity_and_product", "low", "Ambiguous electronics supplier; do not use as switch before validation."),
    "Balterio": decision("wrong_scope_or_unrelated", "T2", "remove_unless_material_traceability_exists", "low", "Laminate flooring brand; not a credible aerospace-seat supplier without material traceability."),
    "Diodes Incorporated": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics, not direct aerospace supplier.", "SRC_DIODES_001", "Diodes Incorporated"),
    "Glatfelter": decision("validated_supplier", "T2", "keep_with_material_scope_check", "medium_high", "Engineered materials/nonwovens supplier; plausible for paper/nonwoven material.", "SRC_GLATFELTER_001", "Glatfelter"),
    "Group Mondi": decision("packaging_or_paper_auxiliary", "PKG", "move_to_packaging_or_auxiliary_flow", "high", "Paper/packaging group; usually packaging/auxiliary unless material paper is deliberate.", "SRC_MONDI_001", "Mondi"),
    "Hexcel Corporation": decision("validated_supplier", "T2", "keep_or_reclassify_T3_composites", "high", "Aerospace composites/carbon fiber supplier.", "SRC_HEXCEL_001", "Hexcel"),
    "Infineon Technologies AG": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics but not direct seat supplier.", "SRC_INFINEON_001", "Infineon"),
    "Intel --> fondée en 1968 qui est le deuxième fabricant mondial de semi-conducteurs.": decision("cots_brand_not_supply_node", "T2", "normalize_or_remove", "medium", "Text contains encyclopedia note; if kept, normalize to Intel and model only as generic semiconductor upstream.", "SRC_INTEL_001", "Intel"),
    "NVIDIA": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_component_supplier", "medium", "Too generic without exact electronic BOM.", "SRC_NVIDIA_001", "NVIDIA"),
    "Pergo": decision("wrong_scope_or_unrelated", "T2", "remove_unless_material_traceability_exists", "low", "Flooring laminate brand; not credible as aerospace-seat supply node without traceability."),
    "ROHM Co. Ltd": decision("validated_supplier_cots_upstream", "T2", "demote_to_electronics_cots_upstream", "medium_high", "Semiconductor supplier; valid upstream electronics but not direct seat supplier.", "SRC_ROHM_001", "ROHM"),
    "Racelogic": decision("wrong_scope_or_unrelated", "T2", "remove_unless_product_traceability_exists", "low", "Data logger/vehicle testing supplier does not fit cable bracket record without exact product proof."),
    "SGL Carbon": decision("validated_supplier", "T2", "keep_or_reclassify_T3_composites", "high", "Carbon/composites materials supplier.", "SRC_HEXCEL_001", "SGL Carbon"),
    "SIKA": decision("validated_supplier", "T2", "keep_with_product_scope_check", "high", "Aerospace adhesives/sealants supplier; verify exact adhesive/film product.", "SRC_SIKA_001", "Sika"),
    "TSMC": decision("cots_brand_not_supply_node", "T2", "replace_with_exact_component_supplier", "medium", "Foundry too far upstream/generic without exact electronic BOM.", "SRC_TSMC_001", "TSMC"),
    "THALES": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "Aerospace/avionics supplier; plausible T1/T2 for IFE/electronics.", "SRC_THALES_001", "Thales"),
    "JAMMY Inc": decision("not_verified_probable_error", "T1", "remove_or_replace_with_JAMCO_if_intended", "low", "Not verifiable as aerospace-seat supplier; likely typo/noise."),
    "Continental": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_display_supplier", "medium", "Real electronics/automotive group but not a qualified aerospace seat supplier by current data."),
    "General Electric": decision("wrong_scope_or_too_broad", "T1", "remove_unless_exact_GE_aerospace_product", "medium", "Too broad and mismatched for silicone/cables without product traceability."),
    "PMV": decision("needs_business_validation", "T1", "verify_exact_legal_entity_and_product", "low", "Ambiguous supplier name."),
    "Valeo": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_product", "medium", "Automotive electronics brand; not a direct aerospace-seat supplier without proof."),
    "Adhetec": decision("validated_supplier", "T1", "keep", "high", "Aerospace adhesive films/decoration supplier.", "SRC_ADHETEC_001", "Adhetec"),
    "ESPACE (France)": decision("duplicate_normalization", "T1", "merge_with_ESPACE", "medium", "Duplicate naming variant; merge into existing ESPACE supplier record."),
    "Honeywell": decision("validated_supplier_with_scope_issue", "T1", "keep_with_product_scope_check", "high", "Aerospace systems/electronics group; exact cable/electronic product still needed.", "SRC_HONEYWELL_001", "Honeywell Aerospace"),
    "KEMKO Aerospace": decision("validated_supplier", "T1", "keep_with_product_scope_check", "medium_high", "Aerospace supplier; exact product/site should be validated.", "SRC_KEMKO_001", "KEMKO Aerospace"),
    "LIEBHERR": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "Aerospace systems supplier; exact ECU/actuation relevance should be validated.", "SRC_LIEBHERR_001", "Liebherr Aerospace"),
    "Madelec Aero": decision("validated_supplier", "T1", "keep", "medium_high", "French aerospace electrical/electronic supplier.", "SRC_MADEL_EC_001", "Madelec Aero"),
    "S.E.L.A": decision("needs_business_validation", "T1", "verify_exact_legal_entity_and_product", "low", "Ambiguous supplier name."),
    "SCHNEIDER": decision("cots_brand_not_supply_node", "T1", "demote_or_remove_unless_exact_part", "medium", "Likely Schneider Electric; too generic as T1 cable supplier."),
    "SCHOTT": decision("validated_supplier", "T1", "keep_with_product_scope_check", "high", "SCHOTT has aviation markets; plausible lighting/glass supplier.", "SRC_SCHOTT_001", "SCHOTT Aviation"),
    "Tyco Electronic": decision("validated_supplier", "T1", "normalize_name", "high", "Normalize to TE Connectivity; aerospace connectors/electronics supplier.", "SRC_TE_001", "TE Connectivity"),
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
        "- Remove generic placeholders such as `Polymere`, `Aluminium`, `Velours`, `Tissus:` from the supplier network.",
        "- Move paper/packaging groups such as Mondi or Smurfit Kappa to packaging/auxiliary unless the paper is explicitly part of the seat material.",
        "- Demote generic electronics brands/foundries to COTS-upstream context unless an exact part supplier is known.",
        "- Normalize noisy names: `Mexichem -> Orbia`, `Toschiba-Shinetsu -> Shin-Etsu Silicones`, `Tyco Electronic -> TE Connectivity`, `Sekisui SPI -> SEKISUI KYDEX`.",
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
