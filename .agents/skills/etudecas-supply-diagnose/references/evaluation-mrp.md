# Évaluer le diagnostic MRP

Trois dossiers synthétiques évaluent le rapprochement de deux stocks simulés, la prévision disponible à la date du calcul et le changement d’un ordre entre deux versions du plan. Ils servent à comparer le comportement de l’agent sur un diagnostic connu. Les références de pièces et les ordres sont fictifs.

Depuis la racine du dépôt, produire le dossier à transmettre à l’agent. Choisir `stock`, `prevision` ou `gel`.

```shell
python -B tools/portfolio/eval_mrp.py prompt stock
python -B tools/portfolio/eval_mrp.py prompt stock --avec-skill
```

Pour chaque condition, ouvrir une conversation vierge avec le même modèle et les mêmes réglages, dans un environnement sans accès au dépôt ni aux skills projet. Transmettre uniquement la sortie de la commande correspondante. Le second dossier inclut les instructions du diagnostic et le contrat de ses tickets. Cette comparaison mesure l’effet des consignes une fois chargées. Pour évaluer leur sélection automatique, observer séparément le choix de skill dans les traces d’une session Codex normale.

Enregistrer la réponse JSON du modèle, puis la noter dans une session distincte.

```shell
python -B tools/portfolio/eval_mrp.py grade stock reponse.json
```

Le résultat donne les champs en échec sur quatre axes : calcul, pièces citées, incertitude et suite de l’investigation. Le code de sortie vaut 0 si les quatre contrôles passent, 1 si un constat ou sa preuve échoue, 2 si la réponse est illisible ou incomplète. Garder les réponses des deux conditions avec la révision du dépôt, le modèle et la date. Répéter la comparaison lorsque le résultat varie entre essais.

Relire la note affichée. Vérifier que le lecteur peut refaire le calcul ou la comparaison de versions, comprendre l’inconnue et savoir quelle décision dépend de la pièce demandée. Une contradiction entre cette note et les constats structurés invalide la restitution orale, même si les quatre contrôles automatiques passent.
