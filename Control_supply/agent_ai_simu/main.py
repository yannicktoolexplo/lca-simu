import os
import json
import re
from crewai import Agent, Task, Crew

# === Chargement de l’environnement ===
def charger_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v

charger_env()
if not os.environ.get("GROQ_API_KEY"):
    raise ValueError("Clé API GROQ_API_KEY manquante dans .env")

# === Configuration LLM (Groq) ===
llm_groq = {
    "provider": "groq",
    "config": {
        "model": "mixtral-8x7b-32768",
        "api_key": os.environ.get("GROQ_API_KEY")
    }
}

# === Définition des agents ===
architecte = Agent(
    role="Architecte logiciel",
    goal="Produire un plan d’architecture balisé et le script main_script_by_agent.py.",
    backstory="Il orchestre la structure logicielle du projet.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

dev = Agent(
    role="Développeur Python",
    goal="Créer le module de simulation statique dans simulateur_statique.py.",
    backstory="Il programme la logique de flux et de stock.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

modeleur = Agent(
    role="Modélisateur dynamique",
    goal="Créer la logique d’événements logistiques dans simulateur_dynamique.py.",
    backstory="Il ajoute des dynamiques réalistes et aléatoires.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

visualiseur = Agent(
    role="Agent visualisation",
    goal="Créer des visualisations Plotly dans visualisation.py.",
    backstory="Il transforme les données en graphes lisibles.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

dashboarder = Agent(
    role="Agent dashboard",
    goal="Créer un dashboard interactif dans dashboard.py avec Streamlit.",
    backstory="Il conçoit l’interface pour piloter la simulation.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

manager = Agent(
    role="Manager de projet",
    goal="Valider la conformité du livrable avec le plan et l’objectif métier.",
    backstory="Il supervise l’intégrité fonctionnelle du simulateur.",
    verbose=True, allow_delegation=False,
    llm_config=llm_groq
)

# === Tâches ===
tasks = [
    Task(
        description="""
Tu dois produire :
1. Un plan d’architecture dans une balise <architecture_plan> avec : nom des fichiers, fonctions attendues, agent responsable.
2. Le fichier main_script_by_agent.py dans une balise <main_script>.
3. Tu ne dois utiliser que les balises demandées. Aucun autre format n’est permis.
""",
        expected_output="Plan JSON + script principal balisés",
        agent=architecte
    ),
    Task(
        description="Créer le fichier <fichier name=\"simulateur_statique.py\">...</fichier> avec les fonctions init_stock() et run_simulation().",
        expected_output="simulateur_statique.py",
        agent=dev
    ),
    Task(
        description="Créer le fichier <fichier name=\"simulateur_dynamique.py\">...</fichier> avec les fonctions inject_events() et update_system().",
        expected_output="simulateur_dynamique.py",
        agent=modeleur
    ),
    Task(
        description="Créer le fichier <fichier name=\"visualisation.py\">...</fichier> avec plot_stock_levels(), plot_deliveries(), plot_stocks().",
        expected_output="visualisation.py",
        agent=visualiseur
    ),
    Task(
        description="Créer le fichier <fichier name=\"dashboard.py\">...</fichier> avec get_simulation_params() et launch_dashboard().",
        expected_output="dashboard.py",
        agent=dashboarder
    ),
    Task(
        description="Valider la cohérence entre le plan, les fichiers générés et l’objectif métier.",
        expected_output="rapport de validation",
        agent=manager
    )
]

# === Exécution de Crew ===
crew = Crew(
    agents=[architecte, dev, modeleur, visualiseur, dashboarder, manager],
    tasks=tasks,
    verbose=True
)

result = crew.kickoff()

# === Extraction des fichiers générés ===
def extraire_et_sauvegarder_fichiers(result, dossier="projet_simu"):
    os.makedirs(dossier, exist_ok=True)

    def nettoyer(code):
        return re.sub(r'^[`\'"]{3,}(python)?|[`\'"]{3,}$', '', code.strip(), flags=re.MULTILINE)

    for task in result.tasks_output:
        raw = getattr(task, "raw", "")

        match_archi = re.search(r"<architecture_plan>(.*?)</architecture_plan>", raw, re.DOTALL)
        if match_archi:
            try:
                plan = json.loads(match_archi.group(1).strip())
                with open(os.path.join(dossier, "architecture_plan.json"), "w", encoding="utf-8") as f:
                    json.dump(plan, f, indent=2)
                print("✅ architecture_plan.json extrait.")
            except Exception as e:
                print("❌ Erreur JSON :", e)

        match_main = re.search(r"<main_script>(.*?)</main_script>", raw, re.DOTALL)
        if match_main:
            code = nettoyer(match_main.group(1))
            with open(os.path.join(dossier, "main_script_by_agent.py"), "w", encoding="utf-8") as f:
                f.write(code)
            print("✅ main_script_by_agent.py extrait.")

        fichiers = re.findall(r'<fichier name="(.*?)">(.*?)</fichier>', raw, re.DOTALL)
        for nom, code in fichiers:
            cleaned = nettoyer(code)
            with open(os.path.join(dossier, nom.strip()), "w", encoding="utf-8") as f:
                f.write(cleaned)
            print(f"✅ Fichier {nom.strip()} extrait.")

    print(f"\n✅ Tous les fichiers ont été extraits dans : {dossier}")

extraire_et_sauvegarder_fichiers(result)
