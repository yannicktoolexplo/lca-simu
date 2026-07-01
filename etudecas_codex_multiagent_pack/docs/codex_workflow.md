# Workflow Codex recommande

## 1. Classer la demande

Choisir le role principal :

- simulation ;
- lot_trace ;
- sensitivity ;
- map_payload ;
- data_knowledge ;
- validation.

## 2. Decouper seulement si utile

Utiliser plusieurs agents quand les perimetres sont independants. Exemple :

- un agent lot trace audite les invariants ;
- un agent map payload corrige le rendu ;
- un agent validation verifie les tests.

Eviter deux agents sur le meme fichier.

## 3. Implementer dans le vrai repo

Le code applicatif vit dans `../etudecas`. Le dossier
`etudecas_codex_multiagent_pack` sert de guide, pas de remplacement.

## 4. Conserver peu de resultats

Les runs complets sont temporaires. Garder par defaut :

- summaries ;
- registries ;
- inputs/configs ;
- payloads compacts necessaires a l'affichage courant.

## 5. Verifier

Commande minimale :

```powershell
python -m unittest discover -s etudecas -p "test*.py" -v
```

Ajouter des controles dedies :

- smoke payload compact ;
- ouverture HTML si map modifiee ;
- invariants de quantite si lot trace modifie ;
- comparaison scenario si sensibilite modifiee.

## 6. Conclure

Toujours mentionner :

- fichiers changes ;
- tests executes ;
- limites ;
- prochaine action utile.
