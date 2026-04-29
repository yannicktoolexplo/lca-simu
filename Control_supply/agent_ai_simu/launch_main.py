import os
import subprocess
import sys

# Obtenir le chemin absolu du fichier main.py
script_dir = os.path.dirname(os.path.abspath(__file__))

# Aller dans ce répertoire
os.chdir(script_dir)
print(f"📁 Positionné dans : {script_dir}")

# Vérifie si le venv existe
venv_path = os.path.join(script_dir, "venv")

if not os.path.exists(venv_path):
    print("⚙️ Création de l'environnement virtuel...")
    subprocess.run([sys.executable, "-m", "venv", "venv"])

# Commandes pour activer le venv selon le système
if os.name == "nt":
    activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
    command = f'cmd /k "{activate_script} & echo 🔥 Environnement activé. Lancez python main.py"'
    os.system(command)
else:
    activate_script = os.path.join(venv_path, "bin", "activate")
    print("🔥 Environnement prêt. Pour activer :")
    print(f"source {activate_script}")
    print("Puis lance : python main.py")
