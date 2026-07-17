#Copier FORMULE 

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
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)
from sympy import Symbol
import re


############# Selection du projet
bd.projects.set_current("LAB")

# We use a separate DB for defining our foreground model / activities
# Choose any name
USER_DB = 'MyForeground'
agb.resetDb(USER_DB)

############# Selection des bases de donnees
ei310=bd.Database("ecoinvent-3.10-cutoff")
db_siege=bd.Database("OPERA_siege")

excel_path = r"C:\Users\tristan.debonnet\OneDrive - Scalian\Documents\01_Projets\02_ACV prospective\opera_v1_bw2.xlsx"
db_name = "MyForeground"
transformations = standard_transformations + (implicit_multiplication_application,)

# === CONFIG ===
bd.projects.set_current("LAB")            # adapte si besoin
excel_path = r"C:\Users\tristan.debonnet\OneDrive - Scalian\Documents\01_Projets\02_ACV prospective\opera_v1_bw2.xlsx"  # <--- change si besoin
db_name = "MyForeground"                  # nom de la base demandée
transformations = standard_transformations + (implicit_multiplication_application,)

#################################################### paramètres python simpy
# === 1) Lecture du fichier et détection automatique de l'entête 
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
df = df.reset_index(drop=True)

def safe_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

df["amount"] = df["amount"].apply(safe_float)

print(f"{len(df)} lignes détectées dans le fichier.")

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

# === 3) Création des variables Python (float ou Symbol) ===
alg_vars = {}

for _, row in df.iterrows():
    orig = str(row['name']).strip()
    amount = row["amount"]
    alg_name = orig_to_alg[orig]

    if amount is not None:
        globals()[alg_name] = amount
        alg_vars[alg_name] = amount
    else:
        sym = Symbol(alg_name)
        globals()[alg_name] = sym
        alg_vars[alg_name] = sym

# === 4) Parsing des formules (optionnel) ===
parsed_formulas = {}
local_dict = {name: alg_vars[orig_to_alg[name]] for name in df["name"] if orig_to_alg.get(name)}

parse_ok = 0
parse_failed = 0

for _, row in df.iterrows():
    orig = str(row['name']).strip()
    formula = row['formula']
    if pd.isna(formula) or not str(formula).strip():
        continue

    alg_name = orig_to_alg[orig]

    try:
        expr = parse_expr(str(formula), local_dict=alg_vars, transformations=transformations, evaluate=True)
        parsed_formulas[alg_name] = expr
        parse_ok += 1
    except Exception as exc:
        parsed_formulas[alg_name] = str(formula)
        parse_failed += 1
        print(f"⚠️ Parsing formule échoué pour '{orig}' : {exc}")


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


############# Aluminium
process_al_rer = agb.findActivity("market for aluminium, primary, ingot", 'IAI Area, EU27 & EFTA', db_name = "ecoinvent-3.10-cutoff")
process_al_america = agb.findActivity("market for aluminium, primary, ingot", 'IAI Area, North America', db_name = "ecoinvent-3.10-cutoff")
process_al_cn = agb.findActivity("aluminium production, primary, ingot", 'CN', db_name = "ecoinvent-3.10-cutoff")
process_al_row = agb.findActivity("market for aluminium, primary, ingot", 'RoW', db_name = "ecoinvent-3.10-cutoff") 

al_switch_param = agb.newEnumParam(
    'al_switch_param',
    values=["eu", "us", "cn","row"], 
    default="eu",
    description="Switch on aluminium mix")
al_mix = agb.newSwitchAct(USER_DB,
    "aluminium mix", 
    al_switch_param, 
    { 
        "eu" : process_al_rer, 
        "us" : process_al_america,  
        "cn": process_al_cn,
        "row": process_al_row
    })

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

############# récupérer formule
pr_accoudoir_allee = [act for act in db_siege if act['name'] == "Accoudoir allee"][0]
#pr_transport_vers_hambourg=   [act for act in db_siege if act['name'] == "transport vers Hambourg"][0]
pr_accoudoir_allee2 = agb.copyActivity(
     USER_DB, # The copy of a background activity is done in our own DB, so that we can safely update it                
     pr_accoudoir_allee, # Initial activity : won't be altered
     "accoudoir allee 2") # New name

pr_accoudoir_allee2.updateExchanges({"market for electricity, low voltage": elec_mix,
                                     "market for aluminium, primary, ingot": al_mix})
print(agb.printAct(pr_accoudoir_allee2))
manip_df=agb.printAct(pr_accoudoir_allee2)

# List of impacts to consider
impacts = agb.findMethods("climate change", mainCat="EF v3.0")
functional_value = 1

result=agb.compute_impacts(
    # Root activity of our inventory
    pr_accoudoir_allee2, 
    # list of impacts to consider
    impacts, 
    elec_switch_param = "fr",
    al_switch_param="us", # Switch electricity mix to France
    # The impaxts will be divided by the functional unit
    functional_unit=functional_value,)




# Create a new activity with the function agb.newActivity
new_activity = agb.newActivity(
                    db_name=USER_DB,         # Database where the new activity is created
                    name="new activity name ",  # Activity name 
                    unit="unit",                # Unit
                    exchanges = {
                        pr_accoudoir_allee2 :  3  }
                    )

result2=agb.compute_impacts(
    # Root activity of our inventory
    new_activity, 
    # list of impacts to consider
    impacts, 
    elec_switch_param = "eu",
    al_switch_param="cn", # Switch electricity mix to France
    # The impaxts will be divided by the functional unit
    functional_unit=functional_value,)

print(result)
print(result2)

# param=agb.list_parameters()
# print(param)


print(manip_df['amount'])