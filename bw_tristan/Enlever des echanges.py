#LCA_ALGB suppression des échanges (électrique et aluminium)

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

############# Selection des bases de donnees
ei310=bd.Database("ecoinvent-3.10-cutoff")
db_siege=bd.Database("OPERA_siege")

pr_transport_vers_hambourg=   [act for act in db_siege if act['name'] == "transport vers Hambourg"][0]
pr_accoudoir_allee = [act for act in db_siege if act['name'] == "Accoudoir allee"][0]
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

# print(alg_air_5086_SF)
pr_transport_vers_hambourg2.addExchanges({elec_mix :  200})

#pr_transport_vers_hambourg2.updateExchanges({"'plywood production' (kilogram, RER, None)": None})
pr_transport_vers_hambourg2.updateExchanges({"plywood production": None})
#print(agb.printAct(pr_transport_vers_hambourg2))

pr_accoudoir_allee2 = agb.copyActivity(
     USER_DB, # The copy of a background activity is done in our own DB, so that we can safely update it                
     pr_accoudoir_allee, # Initial activity : won't be altered
     "accoudoir allee 2") # New name


pr_accoudoir_allee2.updateExchanges({"market for electricity, low voltage": None})
pr_accoudoir_allee2.updateExchanges({"market for aluminium, primary, ingot": None})
pr_accoudoir_allee2.updateExchanges({"treatment of aluminium scrap, new, at refiner": None})
pr_accoudoir_allee2.updateExchanges({"treatment of aluminium scrap, new, at remelter": None})

print(agb.printAct(pr_accoudoir_allee2))

param=agb.list_parameters()
print(param)