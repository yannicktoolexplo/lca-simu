#acv siege

from brightway25 import *
import brightway25 as bw
import bw2analyzer as bwa
import pandas as pd
import bw2calc as bc
import bw2data as bd
import bw2io as bi
#import pbaesa
#from pbaesa import utils
import os 
import lca_algebraic as agb
from sympy import init_printing
from dotenv import load_dotenv

############# Selection du projet
bd.projects.set_current("LAB")


#########LCA_algebraic paramètres
# # This load .env file into os.environ
load_dotenv()
# We use a separate DB for defining our foreground model / activities
# Choose any name
USER_DB = 'MyForeground'

# This is better to cleanup the whole foreground model each time, and redefine it in the notebook (or a python file)
# instead of relying on a state or previous run.
# Any persistent state is prone to errors.
agb.resetDb(USER_DB)

# Parameters are stored at project level : 
# Reset them also
# You may remove this line if you import a project and parameters from an external source (see loadParam(..))
agb.resetParams()

agb.setForeground(USER_DB)
agb.list_databases()

############# Selection des bases de donnees
ei310=bd.Database("ecoinvent-3.10-cutoff")
db_siege=bd.Database("OPERA")

####################################################################### import des parametres
######################################################################
######################################################################
from bw2data.parameters import ProjectParameter, DatabaseParameter, ActivityParameter
import os
import re
import pandas as pd
import bw2data as bd
from bw2data.parameters import DatabaseParameter
import lca_algebraic as agb
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)
from sympy import Symbol

# === CONFIG ===
bd.projects.set_current("LAB")            # adapte si besoin
excel_path = r"C:\Users\tristan.debonnet\OneDrive - Scalian\Documents\01_Projets\02_ACV prospective\opera_v1_bw2.xlsx"  # <--- change si besoin
db_name = "MyForeground"                  # nom de la base demandée
transformations = standard_transformations + (implicit_multiplication_application,)

# === 1) Lecture du fichier et détection automatique de l'entête ===
raw_df = pd.read_excel(excel_path, header=None)
header_row = None
for i, row in raw_df.iterrows():
    row_values = [str(v).strip().lower() for v in row.values if isinstance(v, str)]
    if {"name", "amount", "formula"}.issubset(set(row_values)):
        header_row = i
        break
if header_row is None:
    raise ValueError("Impossible de trouver la ligne contenant 'name', 'amount', 'formula'.")

df = pd.read_excel(excel_path, header=header_row)
df = df[['name', 'amount', 'formula']].dropna(subset=['name'], how='all')
df = df[~df['amount'].astype(str).str.contains(
    "nom database|project parameters|NaN", case=False, na=False)]
df = df.reset_index(drop=True)

def safe_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

df["amount"] = df["amount"].apply(safe_float)
df["database"] = db_name

print(f"🟢 {len(df)} lignes détectées pour import dans la DB '{db_name}'")

# === 2) Sanitisation des noms et mapping original -> alg_<sanitized> ===
def sanitize_for_identifier(s):
    s = str(s).strip()
    s2 = re.sub(r'\W+', '_', s)
    s2 = re.sub(r'__+', '_', s2).strip('_')
    if re.match(r'^\d', s2):
        s2 = '_' + s2
    return s2 or "param"

orig_to_alg = {}
for _, row in df.iterrows():
    orig = str(row['name']).strip()
    base = sanitize_for_identifier(orig)
    alg = f"alg_{base}"
    k = 1
    alg_base = alg
    while alg in orig_to_alg.values():
        k += 1
        alg = f"{alg_base}_{k}"
    orig_to_alg[orig] = alg

# === 3) Création / mise à jour des DatabaseParameter ===
created_bw = updated_bw = 0
for _, row in df.iterrows():
    name = str(row["name"]).strip()
    amount = row["amount"]
    formula = None if pd.isna(row["formula"]) else str(row["formula"]).strip()
    db = row["database"]

    if not name:
        continue

    param, created = DatabaseParameter.get_or_create(
        name=name,
        database=db
    )
    param.amount = amount
    param.formula = formula
    param.save()

    if created:
        created_bw += 1
    else:
        updated_bw += 1

# === 4) Création des paramètres lca_algebraic + variables Python ===
alg_symbols = {}
created_alg = failed_alg = 0
for _, row in df.iterrows():
    orig = str(row['name']).strip()
    amount = row['amount']
    alg_name = orig_to_alg[orig]

    try:
        # crée le paramètre algebraic
        if amount is not None:
            sym = agb.newFloatParam(alg_name, default=amount)
        else:
            sym = agb.newFloatParam(alg_name)

        # enregistre dans le dictionnaire
        alg_symbols[orig] = sym

        # crée la variable Python dynamique
        globals()[alg_name] = sym

        # 🆕 assigne la valeur numérique à la variable Python si connue
        if amount is not None:
            try:
                # Si l’objet a un attribut .value ou similaire
                if hasattr(sym, "setValue"):
                    sym.setValue(amount)
                elif hasattr(sym, "value"):
                    sym.value = amount
                else:
                    # sinon, on remplace la variable Python directement par le float
                    globals()[alg_name] = amount
            except Exception:
                globals()[alg_name] = amount

        created_alg += 1

    except Exception as exc:
        print(f"⚠️ newFloatParam a échoué pour '{alg_name}': {exc}. Création Symbol fallback.")
        sym = Symbol(alg_name)
        alg_symbols[orig] = sym
        globals()[alg_name] = sym
        failed_alg += 1

# === 5) Parser les formules Excel en expressions SymPy ===
parsed_formulas = {}
parse_ok = parse_failed = 0

local_dict = {orig: sym for orig, sym in alg_symbols.items() if sym is not None}

for _, row in df.iterrows():
    orig = str(row['name']).strip()
    formula = None if pd.isna(row['formula']) else str(row['formula']).strip()
    alg_name = orig_to_alg[orig]
    if not formula:
        continue

    try:
        expr = parse_expr(formula, local_dict=local_dict, transformations=transformations, evaluate=True)
        parsed_formulas[alg_name] = expr
        parse_ok += 1
    except Exception as exc:
        print(f"⚠️ Échec parsing formule pour '{orig}' (alg='{alg_name}') : {exc}")
        parsed_formulas[alg_name] = formula
        parse_failed += 1

# === Résumé ===
print("\n===== Résumé import paramètres =====")
print(f"Brightway ({db_name}) : {created_bw} créés, {updated_bw} mis à jour.")
print(f"lca_algebraic : {created_alg} ok, {failed_alg} fallback Symbol.")
print(f"Formules parsées : {parse_ok} OK, {parse_failed} échouées.")
print("Mapping original -> alg :")
for orig, alg in orig_to_alg.items():
    print(f"  {orig} -> {alg}")

print("\n🧩 Variables Python disponibles :")
for name in orig_to_alg.values():
    if name in globals():
        print(f"  {name} = {globals()[name]}")


##########################################################################################################

############# Select processes siege
#for act in db_siege:
#    print(act["name"])
# pr_accoudoir_allee = [act for act in db_siege if act['name'] == "Accoudoir allee  "][0]
# pr_brackets_set= [act for act in db_siege if act['name'] == "Brackets set"][0]
# pr_bumper_version_porte=  [act for act in db_siege if act['name'] == "Bumper version porte"][0]
# pr_capot_NFC= [act for act in db_siege if act['name'] == "Capot NFC"][0]
# pr_ceinture_securite= [act for act in db_siege if act['name'] == "Ceinture de securite"][0]
# pr_commande_actionnement_ECU=[act for act in db_siege if act['name'] == "commande actionnement ECU"][0]
# pr_consommation_passive_siege_pkm= [act for act in db_siege if act['name'] == "consommation passive siege pkm"][0]
# pr_consommation_passive_siege_tkm= [act for act in db_siege if act['name'] == "consommation passive siege tkm"][0]
# pr_coussin_Ottoman= [act for act in db_siege if act['name'] == "Coussin Ottoman"][0]
# pr_coussin_tetiere = [act for act in db_siege if act['name'] == "Coussin tetiere"][0]
# pr_ecran_seat= [act for act in db_siege if act['name'] == "ecran seat"][0]
# pr_energie_infrastructures= [act for act in db_siege if act['name'] == "energie infrastructures"][0]
pr_ens_structure_fauteuil= [act for act in db_siege if act['name'] == "ENS Structure fauteuil "][0]
# pr_ensemble_coque= [act for act in db_siege if act['name'] == "Ensemble coque"][0]
# pr_ensemble_coussin_assise= [act for act in db_siege if act['name'] == "Ensemble coussin assise"][0]
# pr_ensemble_coussin_dossier_v_tetiere= [act for act in db_siege if act['name'] == "Ensemble coussin dossier version tetiere"][0]
# pr_ensemble_coussin_dossier= [act for act in db_siege if act['name'] == "Ensemble coussin dossier"][0]
# pr_ensemble_equipement_lateral= [act for act in db_siege if act['name'] == "Ensemble equipement lateral"][0]
# pr_ensemble_palette_optimisee= [act for act in db_siege if act['name'] == "Ensemble palette optimisee"][0]
# pr_ensemble_porte= [act for act in db_siege if act['name'] == "Ensemble porte"][0]
# pr_ensemble_stowage_lateral= [act for act in db_siege if act['name'] == "Ensemble stowage lateral"][0]
# pr_ensemble_structure_fixe = [act for act in db_siege if act['name'] == "Ensemble structure fixe"][0]
# pr_ensemble_tablette_cocktail= [act for act in db_siege if act['name'] == "Ensemble tablette cocktail"][0]
# pr_ensemble_tablette_repas=   [act for act in db_siege if act['name'] == "Ensemble tablette repas"][0]
# pr_ensemble_tetiere=   [act for act in db_siege if act['name'] == "Ensemble tetiere "][0]
# pr_habillage_sous_fauteuil=    [act for act in db_siege if act['name'] == "Habillage sous fauteuil"][0]
# pr_kerosene_1pkm = [act for act in db_siege if act['name'] == "kerosene, production et combustion, 1pkm eq"][0]
# pr_kerosene_1tkm = [act for act in db_siege if act['name'] == "kerosene, production et combustion, 1tkm eq"][0]
# pr_lightning=[act for act in db_siege if act['name'] == "Lightning"][0]
# pr_manchette_acc_mobile = [act for act in db_siege if act['name'] == "Manchette acc mobile"][0]
# pr_manchette_equipee= [act for act in db_siege if act['name'] == "Manchette equipee"][0]
# pr_nettoyage_an= [act for act in db_siege if act['name'] == "nettoyage/an"][0]
# pr_packaging_fauteuil = [act for act in db_siege if act['name'] == "packaging fauteuil"][0]
# pr_padding= [act for act in db_siege if act['name'] == "Padding"][0]
# pr_papier_fauteuil= [act for act in db_siege if act['name'] == "papier fauteuil "][0]
# pr_production_du_siege=    [act for act in db_siege if act['name'] == "production du siege"][0]
# pr_recyclage_siege=[act for act in db_siege if act['name'] == "Recyclage siege "][0]
# pr_remote_extender_unit=[act for act in db_siege if act['name'] == "remote extender unit"][0]
# pr_renfort_tubulaire= [act for act in db_siege if act['name'] == "Renfort tubulaire"][0]
# pr_seat_power= [act for act in db_siege if act['name'] == "Seat power"][0]
# pr_SFCU=[act for act in db_siege if act['name'] == "SFCU"][0]
# pr_siege_cycle_vie_entier= [act for act in db_siege if act['name'] == "siege cycle de vie "][0]
# pr_stowage_assemblé_porte=   [act for act in db_siege if act['name'] == "Stowage assemblé avec porte"][0]
# pr_structure_Ottoman_horizontale=  [act for act in db_siege if act['name'] == "Structure Ottoman horizontale"][0]
# pr_support_ecran_assemble=   [act for act in db_siege if act['name'] == "Support ecran assemble"][0]
# pr_support_ecran= [act for act in db_siege if act['name'] == "support ecran"][0]
# pr_support_et_clamps= [act for act in db_siege if act['name'] == "Support et clamps"][0]
# pr_support_manchette_equipee= [act for act in db_siege if act['name'] == "Support manchette equipee"][0]
# pr_support_NFC= [act for act in db_siege if act['name'] == "Support NFC"][0]
# pr_systeme_IFE_boitier=    [act for act in db_siege if act['name'] == "systeme IFE boitier"][0]
pr_transport_vers_hambourg=   [act for act in db_siege if act['name'] == "transport vers Hambourg"][0]

############# Select processes 
######## for electricity market
process_elec_fr = [act for act in ei310 if act['name'] == "market for electricity, low voltage" and act["location"]=="FR"][0]
# process_elec_cn = [act for act in ei310 if act['name'] == "market group for electricity, low voltage" and act["location"]=="CN"][0]
# process_elec_rer = [act for act in ei310 if act['name'] == "market group for electricity, low voltage" and act["location"]=="RER"][0]
# process_elec_us = [act for act in ei310 if act['name'] == "market group for electricity, low voltage" and act["location"]=="US"][0]

# ######## for aluminium production
# process_al_rer = [act for act in ei310 if act['name'] == "market for aluminium, primary, ingot" and act["location"]=="IAI Area, EU27 & EFTA"][0]
# process_al_row = [act for act in ei310 if act['name'] == "market for aluminium, primary, ingot" and act["location"]=="RoW"][0]
# process_al_america = [act for act in ei310 if act['name'] == "market for aluminium, primary, ingot" and act["location"]=="IAI Area, North America"][0]
# process_al_cn = [act for act in ei310 if act['name'] == "aluminium production, primary, ingot" and act["location"]=="CN"][0]

############# Selection de la méthode d'ACV --> changement climatique
method = ('EF v3.1', 'climate change', 'global warming potential (GWP100)')

############### Modification process siege

eu_elec = agb.findActivity("market group for electricity, medium voltage", 'RER', db_name = "ecoinvent-3.10-cutoff")
cn_elec= agb.findActivity("market group for electricity, medium voltage", 'CN', db_name = "ecoinvent-3.10-cutoff")
us_elec= agb.findActivity("market group for electricity, medium voltage", 'US', db_name = "ecoinvent-3.10-cutoff")
fr_elec= agb.findActivity("market for electricity, medium voltage", 'FR', db_name = "ecoinvent-3.10-cutoff")

# Switch parameters 
elec_switch_param = agb.newEnumParam(
    'elec_switch_param', 
    values=["us", "eu", "fr","cn"], # If provided as list, all possibilities have te same probability
    default="eu", 
    description="Switch on electricty mix")

# You can create a virtual "switch" activity combining several activities with an Enum parameter
elec_mix = agb.newSwitchAct(USER_DB, 
    "elect mix", # Name
    elec_switch_param, # Sith parameter
    { # Dictionnary of enum values / activities
        "us" : us_elec, # By default associated amount is 1
        "eu" : eu_elec,  
        "fr": fr_elec,
        "cn": cn_elec
    })

################ Modifiy exchanges
pr_transport_vers_hambourg2 = agb.copyActivity(
    USER_DB, # The copy of a background activity is done in our own DB, so that we can safely update it                
    pr_transport_vers_hambourg, # Initial activity : won't be altered
    "Transport vers hambourg 2") # New name


################################################################################## TEST 2 PARAMETRE
# from lca_algebraic import ParamDef
# from bw2data import Database
# # Fonction robuste pour récupérer le vrai nom de l'input
# def get_input_name(exc):
#     inp = exc['input']

#     # Cas tuple (référence à une autre base)
#     if isinstance(inp, tuple):
#         db_name, key = inp
#         try:
#             input_act = Database(db_name).get(key)
#             return input_act['name']
#         except KeyError:
#             # Si l'activité n'existe plus, retourne juste la clé
#             return f"{db_name}, {key}"
    
#     # Cas Activity object ou déjà un dict
#     try:
#         return inp['name']
#     except (TypeError, KeyError):
#         return str(inp)  # fallback en string
# # Construction du DataFrame
# rows = [
#     {
#         "input_name": get_input_name(exc),
#         "formula": exc.get('formula', exc.get('amount', None)),
#         "type": exc.get('type', None),
#         "unit": exc.get('unit', None)
#     }
#     for exc in pr_ens_structure_fauteuil.exchanges()
# ]

# df_exchanges = pd.DataFrame(rows)
# # Filtrer uniquement les formules pour l'échange ciblé
# target_input = "market for electricity"
# formules = df_exchanges[df_exchanges['input_name'].str.contains(target_input)]['formula'].tolist()

# print(formules)
# #print(df_exchanges)
# # Liste avec "inc" dans le nom
# liste_inc = [f for f in formules if "inc" in str(f)]

# # Liste sans "inc" dans le nom
# liste_sans_inc = [f for f in formules if "inc" not in str(f)]

# #print(liste_inc)
# #print(liste_sans_inc)
# total_expr_str = " + ".join([str(f) for f in liste_sans_inc])
# print(total_expr_str)
############################################################################# pAramètre formules en alg_
bug car je n'arrive pas à avoir les paramètres alg_ dans la formule 
from lca_algebraic import ParamDef
from bw2data import Database
import pandas as pd
import re

# --- 1) Fonction pour récupérer le vrai nom de l'input ---
def get_input_name(exc):
    inp = exc["input"]
    if isinstance(inp, tuple):
        db_name, key = inp
        try:
            input_act = bd.Database(db_name).get(key)
            return input_act["name"]
        except KeyError:
            return f"{db_name}, {key}"
    try:
        return inp["name"]
    except (TypeError, KeyError):
        return str(inp)

# --- 2) Construire le DataFrame depuis test_titi ---
rows = [
    {
        "input_name": get_input_name(exc),
        "formula": exc.get("formula", exc.get("amount", None)),
        "type": exc.get("type", None),
        "unit": exc.get("unit", None),
    }
    for exc in pr_ens_structure_fauteuil.exchanges()
]

df_exchanges = pd.DataFrame(rows)

# --- 3) Filtrer pour l’input ciblé (ou tous) ---
target_input = "market for electricity"  # adapte si besoin
df_target = df_exchanges[df_exchanges["input_name"].str.contains(target_input, case=False, na=False)]

# --- 4) Construire la formule totale (sans "inc") ---
liste_sans_inc = [f for f in df_target["formula"].tolist() if "inc" not in str(f)]
total_expr_str = " + ".join([str(f) for f in liste_sans_inc])
print("Formule d'origine :", total_expr_str)

# --- 5) Remplacer les noms par alg_... ---
def replace_params_with_alg(formula, orig_to_alg):
    if formula is None:
        return formula
    if not isinstance(formula, str):
        return str(formula)
    if "alg_" in formula:
        return formula
    keys = sorted([k for k in orig_to_alg.keys() if k], key=lambda s: -len(s))
    escaped = [re.escape(k) for k in keys]
    pattern = re.compile(r"(?<!\w)(" + "|".join(escaped) + r")(?!\w)")
    def _repl(m):
        found = m.group(1)
        alg = orig_to_alg.get(found)
        if alg is None:
            for k in orig_to_alg:
                if k.lower() == found.lower():
                    alg = orig_to_alg[k]
                    break
        return alg if alg is not None else found
    return pattern.sub(_repl, formula)

total_expr_alg = replace_params_with_alg(total_expr_str, orig_to_alg)
print("Formule adaptée :", total_expr_alg)

# --- 6) Évaluer la formule avec les variables Python alg_... déjà créées ---
local_ns = {name: globals().get(name) for name in set(orig_to_alg.values())}

try:
    result = eval(total_expr_alg, {}, local_ns)
    print("Résultat numérique :", result)
except NameError as e:
    print("⚠️ NameError :", e)
    # vérifier les variables manquantes
    pattern_vars = re.compile(r"\balg_[A-Za-z_]\w*\b")
    used_vars = set(pattern_vars.findall(total_expr_alg))
    missing = [v for v in used_vars if local_ns.get(v) is None]
    print("Variables manquantes :", missing)


print("Formule d’origine :", total_expr_str)
print("Formule adaptée :", total_expr_alg)
############### LCA algebraic: load parameters
# Load parameters previously  persisted in the dabatase.
agb.loadParams()

###############" LCA Algebraic activities"
# Print_act displays activities as tables
#print(agb.printAct(pr_transport_vers_hambourg2))


############# Calculs ACV 
# lca = bc.LCA({process_elec_fr: 1}, method)
# lca.lci()
# lca.lcia()
# print(lca.score)

from sympy import symbols, sympify

# Définir tous les paramètres utilisés comme symboles SymPy
#elec_acier, steel_param = symbols('elec_acier steel_param')
print(total_expr_str)
from sympy.parsing.sympy_parser import parse_expr
express=parse_expr(total_expr_str)
# Update exchanges by their name 
print(express)
pr_transport_vers_hambourg2.addExchanges({elec_mix :  express})
print(agb.printAct(pr_transport_vers_hambourg2))
df_test = agb.printAct(pr_transport_vers_hambourg2)
print(df_test.iloc[:, 1])

# # List of impacts to consider
# impacts = agb.findMethods("climate change", mainCat="EF v3.0")
# functional_value = 1

# agb.compute_impacts(
#     # Root activity of our inventory
#     pr_transport_vers_hambourg2, 
#     # list of impacts to consider
#     impacts, 
#     # The impaxts will be divided by the functional unit
#     functional_unit=functional_value,)
print(alg_se_air_alu5086)
