# Prompt Codex - Map payload

Tu es l'agent map_payload du vrai repo Etudecas.

Objectif : ameliorer la carte HTML sans perdre l'interactivite metier.

A inspecter :

- `etudecas/visualization/maps/build_supplychain_worldmap.py`
- `etudecas/visualization/maps/html_payload_tools.py`
- tests `etudecas/visualization/maps/test_*.py`
- HTML courant si necessaire.

A faire :

- separer payload et rendu quand possible ;
- garder un HTML autonome raisonnable ;
- charger les details lourds a la demande ;
- verifier les onglets critiques.

Validation :

- tests payload ;
- smoke navigateur si l'affichage change.
