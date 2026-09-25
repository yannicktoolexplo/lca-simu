# Déploiement natif Codex pour Etudecas

Le travail courant utilise les profils et skills installés à la racine du
dépôt. Ce dossier conserve les **neuf fichiers de déploiement révisables** sous
`native/`, avec trois fichiers à sa racine : ce guide, `AGENTS.md` et
`MANIFEST.json`.

- [Consignes](AGENTS.md) : routage et responsabilités.
- [Configuration installée](../.codex/config.toml) et
  [profils installés](../.codex/agents/) : quatre rôles natifs.
- [Skills installés](../.agents/skills/) : orchestration, qualification et revue
  de carte.
- [Déploiement à examiner](native/) : copie de préparation pour un autre poste.

Le [guide opérationnel](../etudecas/docs/MULTI_AGENT_OPERATIONNEL.md) décrit
l'installation, les contrats de délégation et la toolbox. Fusionner les fichiers
de `native/` avec les consignes du poste cible après examen ; ne pas écraser
automatiquement la configuration installée.

Depuis la racine du dépôt, le diagnostic de l'installation est :

```powershell
python -B -m etudecas.toolbox doctor
```

Il produit un rapport ; il ne prouve pas à lui seul la qualité du moteur.
Les vérifications suivent la
[procédure de tests ciblés](../etudecas/docs/TEST_VALIDATION.md), après relecture
des cas et fixtures. Les suites globales et essais d'altération de fichiers
ne sont pas des commandes de validation autorisées.

Les anciens rôles, prompts et skills documentaires sont dans les
[archives](../etudecas/archive/README.md), avec leurs chemins d'origine.
La démonstration `etudecas_agentkit`, retirée auparavant, est récupérable dans
Git au commit `34c8e5dc37cd66d606c9d90b80ad0a51a2a61a35`.
Ses contrats génériques conservés dans
`etudecas/toolbox/validation_contracts.py` ne remplacent pas les indicateurs
industriels ni leur calibration.
